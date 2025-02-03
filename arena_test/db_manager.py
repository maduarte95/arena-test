from pymongo import MongoClient
from datetime import datetime
import json
from typing import Dict, List, Optional
import os
from bson.objectid import ObjectId

class GameDataManager:
    def __init__(self, connection_string: str = None):
        """Initialize MongoDB connection"""
        if connection_string is None:
            connection_string = os.getenv('MONGODB_URI')
            
        if not connection_string:
            raise ValueError("MongoDB connection string not found")
            
        self.client = MongoClient(connection_string)
        self.db = self.client.ai_arena
        
        # Create indexes for better query performance
        self.db.games.create_index("created_at")
        self.db.turns.create_index("game_id")
        self.db.conversations.create_index([("game_id", 1), ("turn_number", 1)])
        self.db.users.create_index("username", unique=True)
    
    def create_user(self, username: str, password_hash: str) -> bool:
        """Create a new user"""
        try:
            self.db.users.insert_one({
                'username': username,
                'password_hash': password_hash,
                'created_at': datetime.utcnow(),
                'games_played': 0,
                'games_won': 0
            })
            return True
        except Exception:
            return False
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user data"""
        return self.db.users.find_one({'username': username}, {'_id': 0})
    
    def update_user_stats(self, username: str, won: bool):
        """Update user statistics"""
        self.db.users.update_one(
            {'username': username},
            {
                '$inc': {
                    'games_played': 1,
                    'games_won': 1 if won else 0
                }
            }
        )
    
    def create_game_session(self, initial_state: Dict, username: str = None) -> str:
        """Create a new game session"""
        game_doc = {
            'created_at': datetime.utcnow(),
            'status': 'in_progress',
            'initial_state': initial_state,
            'current_turn': 0,
            'winner': None,
            'final_state': None,
            'prompts': {},
            'total_turns': 0,
            'player_a_username': username
        }
        
        result = self.db.games.insert_one(game_doc)
        return str(result.inserted_id)
    
    def save_turn_data(self, game_id: str, turn_data: Dict):
        """Save data for a single turn"""
        # Increment turn counter
        self.db.games.update_one(
            {'_id': ObjectId(game_id)},
            {'$inc': {'current_turn': 1, 'total_turns': 1}}
        )
        
        # Get current turn number
        game = self.db.games.find_one({'_id': ObjectId(game_id)})
        turn_number = game['current_turn']
        
        # Save turn state
        turn_doc = {
            'game_id': ObjectId(game_id),
            'turn_number': turn_number,
            'player_state': turn_data['game_state'],
            'actions': turn_data['actions'],
            'timestamp': datetime.utcnow()
        }
        
        self.db.turns.insert_one(turn_doc)
        
        # Save conversation separately
        if 'conversation' in turn_data:
            conv_doc = {
                'game_id': ObjectId(game_id),
                'turn_number': turn_number,
                'messages': turn_data['conversation'],
                'timestamp': datetime.utcnow()
            }
            self.db.conversations.insert_one(conv_doc)
    
    def save_conversation(self, game_id: str, turn_number: int, 
                         messages: List[Dict], llm_params: Dict):
        """Save conversation data including LLM parameters"""
        conv_doc = {
            'game_id': ObjectId(game_id),
            'turn_number': turn_number,
            'messages': messages,
            'llm_params': llm_params,
            'timestamp': datetime.utcnow()
        }
        
        self.db.conversations.insert_one(conv_doc)
    
    def save_prompts(self, game_id: str, prompts: Dict):
        """Save prompt templates used in the game"""
        self.db.games.update_one(
            {'_id': ObjectId(game_id)},
            {'$set': {'prompts': prompts}}
        )
    
    def end_game(self, game_id: str, winner: str, final_state: Dict):
        """Record game completion and update user stats"""
        self.db.games.update_one(
            {'_id': ObjectId(game_id)},
            {
                '$set': {
                    'status': 'completed',
                    'end_time': datetime.utcnow(),
                    'winner': winner,
                    'final_state': final_state
                }
            }
        )
        
        # Update user stats if game was played by a registered user
        game = self.db.games.find_one({'_id': ObjectId(game_id)})
        if game and 'player_a_username' in game:
            won = winner == "Player A"
            self.update_user_stats(game['player_a_username'], won)
    
    def get_game_history(self, game_id: str) -> Optional[Dict]:
        """Retrieve complete game history"""
        # Get base game data
        game = self.db.games.find_one({'_id': ObjectId(game_id)})
        if not game:
            return None
            
        # Get all turns
        turns = list(self.db.turns.find(
            {'game_id': ObjectId(game_id)},
            {'_id': 0}
        ).sort('turn_number', 1))
        
        # Get all conversations
        conversations = list(self.db.conversations.find(
            {'game_id': ObjectId(game_id)},
            {'_id': 0}
        ).sort('turn_number', 1))
        
        # Convert ObjectId to string for JSON serialization
        game['_id'] = str(game['_id'])
        
        return {
            'game_info': game,
            'turns': turns,
            'conversations': conversations
        }
    
    def get_recent_games(self, limit: int = 10) -> List[Dict]:
        """Get most recent games"""
        games = list(self.db.games.find(
            {},
            {'_id': 1, 'created_at': 1, 'status': 1, 'winner': 1, 'total_turns': 1, 'player_a_username': 1}
        ).sort('created_at', -1).limit(limit))
        
        # Convert ObjectId to string
        for game in games:
            game['_id'] = str(game['_id'])
            
        return games
    
    def get_user_stats(self) -> List[Dict]:
        """Get statistics for all users"""
        return list(self.db.users.find(
            {},
            {
                '_id': 0,
                'username': 1,
                'games_played': 1,
                'games_won': 1,
                'created_at': 1
            }
        ))