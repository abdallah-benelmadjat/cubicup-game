import os
import numpy as np
from sb3_contrib import MaskablePPO
from .base import BaseBot
from cubicup_game import get_all_positions, str_to_pos, pos_to_str, YELLOW, BLUE

class RLBot(BaseBot):
    """
    CubiCup bot that uses a trained MaskablePPO model.
    """
    def __init__(self, model_path="models/ppo_cubicup_final.zip", n=6):
        self.n = n
        self.positions = get_all_positions(n)
        self.num_positions = len(self.positions)
        self.pos_to_idx = {pos: i for i, pos in enumerate(self.positions)}
        self.idx_to_pos = {i: pos for i, pos in enumerate(self.positions)}
        
        if os.path.exists(model_path):
            self.model = MaskablePPO.load(model_path)
        else:
            print(f"Warning: Model not found at {model_path}. RLBot will be untrained.")
            self.model = None

    def _get_obs(self, state):
        obs = np.zeros(self.num_positions + 3, dtype=np.int32)
        board = state['board']
        my_color = state['current_player']
        opp_color = BLUE if my_color == YELLOW else YELLOW
        
        for pos_str, color in board.items():
            pos = str_to_pos(pos_str)
            idx = self.pos_to_idx[pos]
            if color == my_color:
                obs[idx] = 1
            elif color == opp_color:
                obs[idx] = 2
            else:
                obs[idx] = 0
        
        obs[self.num_positions] = state['cubes_left'][my_color]
        obs[self.num_positions + 1] = state['cubes_left'][opp_color]
        obs[self.num_positions + 2] = 1 if state['mandatory'] else 0
        return obs

    def _get_mask(self, state):
        mask = np.zeros(self.num_positions, dtype=bool)
        for move_str in state['legal_moves']:
            pos = str_to_pos(move_str)
            mask[self.pos_to_idx[pos]] = True
        return mask

    def choose_move(self, state):
        if self.model is None:
            # Fallback to random if model is not loaded
            import random
            return random.choice(state['legal_moves'])
            
        obs = self._get_obs(state)
        mask = self._get_mask(state)
        
        action, _states = self.model.predict(obs, action_masks=mask, deterministic=True)
        
        move_pos = self.idx_to_pos[int(action)]
        return pos_to_str(move_pos)
