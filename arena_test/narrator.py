# narrator.py
from dataclasses import dataclass
from typing import List, Dict
from anthropic import Anthropic
import json
import streamlit as st
from prompt_manager import PromptType

class GameNarrator:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
    
    async def generate_turn_summary(self, recent_actions: List[Dict], game_state: Dict) -> str:
        """
        Generate a narrative summary of recent game events
        """
        try:
            selected_prompt = st.session_state.prompt_manager.get_prompt(
                PromptType.NARRATOR,
                st.session_state.selected_prompts[PromptType.NARRATOR]
            )
            
            formatted_prompt = st.session_state.prompt_manager.format_prompt(
                selected_prompt,
                game_state=json.dumps(game_state, indent=2),
                recent_actions=json.dumps(recent_actions, indent=2)
            )
            
        except (KeyError, AttributeError) as e:
            # Fallback prompt if the prompt system fails
            formatted_prompt = f"""As the narrator of an AI Arena game, create an engaging summary of recent events.
            Focus on public actions and their results, while maintaining any strategic secrets.
            
            Current game state:
            {json.dumps(game_state, indent=2)}
            
            Recent actions:
            {json.dumps(recent_actions, indent=2)}
            
            Create a brief, engaging narrative that:
            1. Describes what happened in an exciting way
            2. Maintains dramatic tension
            3. Only reveals public information
            4. Connects events in a coherent narrative thread
            5. Highlights significant state changes (HP, position, etc.)
            """
        
        response = self.client.messages.create(
            max_tokens=500,
            messages=[{"role": "user", "content": formatted_prompt}],
            model="claude-3-sonnet-20240229"
        )
        
        return response.content[0].text