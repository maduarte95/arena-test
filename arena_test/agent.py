from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from anthropic import Anthropic
import json
import logging
from game_state import PlayerType
from prompt_manager import PromptType
import streamlit as st

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GameMaster:
    def __init__(self, player_name: str, api_key: str):
        self.player_name = player_name
        self.client = Anthropic(api_key=api_key)
        self.conversation_history = []
        self.current_turn = 0  # Added this attribute
    
    def format_history_for_prompt(self) -> str:
        if not self.conversation_history:
            return "No previous conversation."
            
        formatted_history = []
        for turn in self.conversation_history:
            formatted_history.append(
                f"Turn {turn['turn_number']}:\n"
                f"Player: {turn['player_message']}\n"
                f"GM: {turn['gm_response']}\n"
            )
        return "\n".join(formatted_history)
    
    async def process_turn_streaming(self, player_message: str, game_state: Dict, 
                                   update_placeholder_fn) -> Tuple[str, Dict]:
        # Get the selected prompt from session state
        selected_prompt = st.session_state.prompt_manager.get_prompt(
            PromptType.GAME_MASTER,
            st.session_state.selected_prompts[PromptType.GAME_MASTER]
        )
        
        formatted_prompt = st.session_state.prompt_manager.format_prompt(
            selected_prompt,
            player_name=self.player_name,
            conversation_history=self.format_history_for_prompt(),
            game_state=json.dumps(game_state, indent=2),
            player_message=player_message
        )
        
        # Add the updates section template
        formatted_prompt += """
        
        After your response, provide a JSON object with state updates in the format:
        ###Updates
        {
            "hp_changes": {
                "player_a": 0,
                "player_b": 0
            },
            "position_changes": {
                "player_a": [0, 0],
                "player_b": [0, 0]
            },
            "custom_stat_changes": {
                "player_a": {},
                "player_b": {}
            }
        }
        """
        
        logger.info("\n" + "="*50 + "\nFULL GM CONTEXT:\n" + "="*50)
        logger.info(formatted_prompt)
        
        accumulated_response = ""
        
        stream = self.client.messages.create(
            max_tokens=1000,
            messages=[{"role": "user", "content": formatted_prompt}],
            model="claude-3-sonnet-20240229",
            stream=True
        )

        for event in stream:
            if event.type == "content_block_delta":
                text_delta = event.delta.text
                if text_delta:
                    accumulated_response += text_delta
                    update_placeholder_fn(accumulated_response)
        
        logger.info("\n" + "="*50 + "\nFINAL RESPONSE:\n" + "="*50)
        logger.info(accumulated_response)
        
        # Store the conversation turn
        self.conversation_history.append({
            "player_message": player_message,
            "gm_response": accumulated_response,
            "turn_number": self.current_turn,
            "game_state_snapshot": game_state
        })
        self.current_turn += 1
        
        # Parse updates from response
        updates = {}
        if "###Updates" in accumulated_response:
            try:
                updates_text = accumulated_response.split("###Updates")[1].strip()
                updates = json.loads(updates_text)
                logger.info("\n" + "="*50 + "\nPARSED UPDATES:\n" + "="*50)
                logger.info(json.dumps(updates, indent=2))
            except Exception as e:
                logger.error(f"Error parsing updates: {e}")
                updates = {
                    "hp_changes": {"player_a": 0, "player_b": 0},
                    "position_changes": {"player_a": [0, 0], "player_b": [0, 0]},
                    "custom_stat_changes": {"player_a": {}, "player_b": {}}
                }
        
        return accumulated_response.split("###Updates")[0].strip(), updates