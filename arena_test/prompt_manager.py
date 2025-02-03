from dataclasses import dataclass
from typing import Dict, List
import yaml
import json
import os
from enum import Enum

class PromptType(Enum):
    GAME_MASTER = "game_master"
    PLAYER_B = "player_b"
    NARRATOR = "narrator"

@dataclass
class Prompt:
    name: str
    content: str
    description: str
    type: PromptType

class PromptManager:
    def __init__(self, prompts_dir: str = "prompt_templates"):
        self.prompts_dir = prompts_dir
        self.prompts: Dict[PromptType, List[Prompt]] = {
            prompt_type: [] for prompt_type in PromptType
        }
        self.load_prompts()

    def load_prompts(self):
        """Load all prompts from YAML files in the prompts directory"""
        if not os.path.exists(self.prompts_dir):
            os.makedirs(self.prompts_dir)
            self._create_default_prompts()
        
        for filename in os.listdir(self.prompts_dir):
            if filename.endswith('.yaml'):
                with open(os.path.join(self.prompts_dir, filename), 'r') as f:
                    prompt_data = yaml.safe_load(f)
                    prompt = Prompt(
                        name=prompt_data['name'],
                        content=prompt_data['content'],
                        description=prompt_data['description'],
                        type=PromptType(prompt_data['type'])
                    )
                    self.prompts[prompt.type].append(prompt)

    def _create_default_prompts(self):
        """Create default prompt files if none exist"""
        default_prompts = {
            "game_master_default.yaml": {
                "name": "Default Game Master",
                "type": "game_master",
                "description": "Default prompt for the Game Master role",
                "content": """You are the Game Master for {player_name} in an AI Arena game.
        
                Previous conversation history:
                {conversation_history}
                
                Current game state:
                {game_state}
                
                Rules:
                - No actions can confer infinite HP
                - No actions can drain opponent's HP to zero instantly
                - Actions should be evaluated based on narrative merit and creativity
                - Maintain consistency with previous narrative elements
                - Reference previous conversation elements when relevant
                
                Player's current message: {player_message}
                
                Respond in character as the Game Master, maintaining narrative continuity with previous interactions."""
            },
            "player_b_default.yaml": {
                "name": "Default Player B",
                "type": "player_b",
                "description": "Default prompt for the AI Player B",
                "content": """You are playing as Player B in an AI Arena game. You need to respond to the current 
                game state and your opponent's actions with a strategic move of your own.

                Current game state:
                {game_state}

                Recent actions summary:
                {action_summary}

                Previous narrative history:
                {narrative_history}

                Generate a response that includes:
                1. A narrative description of your strategic thinking and approach
                2. The specific action you choose to take
                3. Expected impact on the game state"""
            },
            "narrator_default.yaml": {
                "name": "Default Narrator",
                "type": "narrator",
                "description": "Default prompt for the game narrator",
                "content": """As the narrator of an AI Arena game, create an engaging summary of recent events.
                Focus on public actions and their results, while maintaining any strategic secrets.
                
                Current game state:
                {game_state}
                
                Recent actions:
                {recent_actions}
                
                Create a brief, engaging narrative that:
                1. Describes what happened in an exciting way
                2. Maintains dramatic tension
                3. Only reveals public information
                4. Connects events in a coherent narrative thread
                5. Highlights significant state changes"""
            }
        }

        for filename, content in default_prompts.items():
            with open(os.path.join(self.prompts_dir, filename), 'w') as f:
                yaml.dump(content, f)

    def get_prompts(self, prompt_type: PromptType) -> List[Prompt]:
        """Get all prompts of a specific type"""
        return self.prompts[prompt_type]

    def get_prompt(self, prompt_type: PromptType, name: str) -> Prompt:
        """Get a specific prompt by type and name"""
        for prompt in self.prompts[prompt_type]:
            if prompt.name == name:
                return prompt
        raise ValueError(f"No prompt found with name {name} and type {prompt_type}")

    def add_prompt(self, prompt: Prompt):
        """Add a new prompt and save it to a file"""
        filename = f"{prompt.name.lower().replace(' ', '_')}.yaml"
        prompt_data = {
            "name": prompt.name,
            "type": prompt.type.value,
            "description": prompt.description,
            "content": prompt.content
        }
        
        with open(os.path.join(self.prompts_dir, filename), 'w') as f:
            yaml.dump(prompt_data, f)
        
        self.prompts[prompt.type].append(prompt)

    def format_prompt(self, prompt: Prompt, **kwargs) -> str:
        """Format a prompt with the provided arguments"""
        return prompt.content.format(**kwargs)