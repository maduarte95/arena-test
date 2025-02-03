from dataclasses import dataclass, field
from typing import Dict, Tuple
from anthropic import Anthropic
import json
import logging
from prompt_manager import PromptType
import streamlit as st

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PlayerBAgent:

    def __init__(self, api_key: str):
        logger.info("Initializing PlayerBAgent")
        self.client = Anthropic(api_key=api_key)
        self.narrative_history = []
    
    async def generate_turn(self, game_state: Dict, action_summary: str) -> Tuple[str, Dict]:
        selected_prompt = st.session_state.prompt_manager.get_prompt(
            PromptType.PLAYER_B,
            st.session_state.selected_prompts[PromptType.PLAYER_B]
        )
        
        formatted_prompt = st.session_state.prompt_manager.format_prompt(
            selected_prompt,
            game_state=json.dumps(game_state, indent=2),
            action_summary=action_summary,
            narrative_history=self._format_narrative_history()
        )
        
        # Add the updates section template
        formatted_prompt += """
        
        Provide your response followed by a JSON updates object in the format:
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
        
        logger.info("\n" + "="*50 + "\nPLAYER B GENERATING TURN\n" + "="*50)
        logger.info(f"Using prompt:\n{formatted_prompt}")
        
        # Note: Create is not async, so we don't use await here
        try:
            response = self.client.messages.create(
                max_tokens=1000,
                messages=[{"role": "user", "content": formatted_prompt}],
                model="claude-3-sonnet-20240229"
            )
            logger.info("\n" + "="*50 + "\nRECEIVED API RESPONSE:\n" + "="*50)
            logger.info(f"Full response object: {response}")
            logger.info(f"Response content: {response.content}")
            
            # Get the first content block's text
            content = response.content[0].text
            logger.info(f"\nExtracted content text: {content}")
            
            # Split the response into narrative and updates
            parts = content.split("###Updates")
            narrative = parts[0].strip()
            logger.info(f"\nExtracted narrative: {narrative}")
            
            try:
                updates = json.loads(parts[1].strip())
                logger.info(f"\nParsed updates: {json.dumps(updates, indent=2)}")
            except (json.JSONDecodeError, IndexError) as e:
                logger.error(f"Error parsing updates: {e}")
                logger.error(f"Raw updates text: {parts[1] if len(parts) > 1 else 'No updates section found'}")
                # Provide default updates if parsing fails
                updates = {
                    "hp_changes": {"player_a": 0, "player_b": 0},
                    "position_changes": {"player_a": [0, 0], "player_b": [0, 0]},
                    "custom_stat_changes": {"player_a": {}, "player_b": {}}
                }
        
        except Exception as e:
            logger.error(f"Error during API call: {e}")
            raise
        
        self.narrative_history.append({
            "turn_narrative": narrative,
            "game_state_snapshot": game_state,
            "updates": updates
        })
        
        logger.info("\n" + "="*50 + "\nCOMPLETING TURN\n" + "="*50)
        logger.info(f"Final narrative length: {len(narrative)}")
        logger.info(f"Final updates: {json.dumps(updates, indent=2)}")
        
        return narrative, updates
    
    def _format_narrative_history(self) -> str:
        if not self.narrative_history:
            return "No previous actions."
            
        formatted = []
        for entry in self.narrative_history:
            formatted.append(f"Turn narrative:\n{entry['turn_narrative']}\n")
        return "\n".join(formatted)