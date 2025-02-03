from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from enum import Enum

class PlayerType(Enum):
    A = "player_a"
    B = "player_b"

@dataclass
class TurnAction:
    player: PlayerType
    narrative: str
    state_updates: Dict
    turn_number: int

@dataclass
class PlayerState:
    name: str
    hp: int
    position: tuple[int, int]
    custom_stats: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "hp": self.hp,
            "position": list(self.position),
            "custom_stats": self.custom_stats
        }

class GameState:
    def __init__(self):
        self.player_a = PlayerState("Player A", 100, (3, 4))
        self.player_b = PlayerState("Player B", 100, (7, 4))
        self.turn_number = 0
        self.current_player: PlayerType = None
        self.action_history: List[TurnAction] = []
        self.public_narrative: List[str] = []
    
    def to_dict(self) -> Dict:
        return {
            "player_a": self.player_a.to_dict(),
            "player_b": self.player_b.to_dict(),
            "turn_number": self.turn_number,
            "current_player": self.current_player.value if self.current_player else None,
            "public_narrative": self.public_narrative
        }

    def update_state(self, updates: Dict, player: PlayerType, narrative: str):
        # Handle HP changes
        if 'hp_changes' in updates:
            for player_id, change in updates['hp_changes'].items():
                target = self.player_a if player_id == "player_a" else self.player_b
                target.hp = max(0, target.hp + change)
        
        # Handle position changes
        if 'position_changes' in updates:
            for player_id, change in updates['position_changes'].items():
                target = self.player_a if player_id == "player_a" else self.player_b
                dx, dy = change
                current_x, current_y = target.position
                new_x = max(0, min(9, current_x + dx))
                new_y = max(0, min(9, current_y + dy))
                target.position = (new_x, new_y)
        
        # Handle custom stat changes
        if 'custom_stat_changes' in updates:
            for player_id, stats in updates['custom_stat_changes'].items():
                target = self.player_a if player_id == "player_a" else self.player_b
                target.custom_stats.update(stats)
        
        # Record the action
        self.action_history.append(TurnAction(
            player=player,
            narrative=narrative,
            state_updates=updates,
            turn_number=self.turn_number
        ))
        
        self.turn_number += 1
        self.current_player = PlayerType.B if player == PlayerType.A else PlayerType.A

    def get_recent_actions(self) -> List[Dict]:
        """Returns recent actions"""
        actions = []
        for action in self.action_history:
            action_dict = {
                "player": action.player.value,
                "narrative": action.narrative,
                "turn_number": action.turn_number
            }
            actions.append(action_dict)
        return actions