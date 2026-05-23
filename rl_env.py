import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random
from cubicup_game import (
    fresh_state, apply_move, get_legal_moves, state_to_api,
    get_all_positions, YELLOW, BLUE, str_to_pos, pos_to_str
)

class CubiCupEnv(gym.Env):
    """
    Gymnasium environment for CubiCup.
    The agent always plays as one color (assigned at reset).
    The opponent bot plays automatically during step().
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, opponent_bot=None, n=6):
        super(CubiCupEnv, self).__init__()
        self.n = n
        self.positions = get_all_positions(n)
        self.num_positions = len(self.positions)
        self.pos_to_idx = {pos: i for i, pos in enumerate(self.positions)}
        self.idx_to_pos = {i: pos for i, pos in enumerate(self.positions)}
        
        # Observation space: 
        # 0-55: Board positions (0=empty, 1=self, 2=opponent)
        # 56: self cubes left
        # 57: opponent cubes left
        # 58: is mandatory (0 or 1)
        self.observation_space = spaces.Box(
            low=0, high=28, shape=(self.num_positions + 3,), dtype=np.int32
        )
        
        # Action space: 56 possible positions
        self.action_space = spaces.Discrete(self.num_positions)
        
        self.opponent_bot = opponent_bot
        self.state = None
        self.agent_color = None
        self.opponent_color = None

    def _get_obs(self):
        obs = np.zeros(self.num_positions + 3, dtype=np.int32)
        board = self.state['board']
        for pos, color in board.items():
            idx = self.pos_to_idx[pos]
            if color == self.agent_color:
                obs[idx] = 1
            elif color == self.opponent_color:
                obs[idx] = 2
            else:
                obs[idx] = 0
        
        obs[self.num_positions] = self.state['cubes_left'][self.agent_color]
        obs[self.num_positions + 1] = self.state['cubes_left'][self.opponent_color]
        obs[self.num_positions + 2] = 1 if self.state['mandatory'] else 0
        return obs

    def action_masks(self):
        mask = np.zeros(self.num_positions, dtype=bool)
        legal_moves = get_legal_moves(self.state)
        for move_pos in legal_moves:
            mask[self.pos_to_idx[move_pos]] = True
        return mask

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
        self.state = fresh_state(n=self.n)
        # Randomly assign agent color
        self.agent_color = random.choice([YELLOW, BLUE])
        self.opponent_color = BLUE if self.agent_color == YELLOW else YELLOW
        
        # If it's opponent's turn first, they play until it's agent's turn
        while self.state['current_player'] == self.opponent_color and self.state['terminal'] is None:
            self._opponent_move()
            
        return self._get_obs(), {}

    def _opponent_move(self):
        if self.opponent_bot is None:
            # Fallback to random if no bot provided
            legal = get_legal_moves(self.state)
            move = random.choice(legal)
        else:
            api_state = state_to_api(self.state, self.opponent_color)
            result = self.opponent_bot.choose_move(api_state)
            move_str = result[0] if isinstance(result, (tuple, list)) else result
            move = str_to_pos(move_str)
            
        self.state = apply_move(self.state, move)

    def step(self, action):
        move = self.idx_to_pos[action]
        legal_moves = get_legal_moves(self.state)
        
        # Check if move is legal
        if move not in legal_moves:
            # This should be handled by action masking in the trainer, 
            # but we'll add a safety check.
            return self._get_obs(), -10.0, True, False, {"error": "illegal_move"}
        
        # Apply agent move
        self.state = apply_move(self.state, move)
        
        # Opponent turns
        while self.state['current_player'] == self.opponent_color and self.state['terminal'] is None:
            self._opponent_move()
            
        # Check termination
        terminated = self.state['terminal'] is not None
        reward = 0.0
        if terminated:
            if self.state['terminal'] == self.agent_color:
                reward = 1.0
            elif self.state['terminal'] == self.opponent_color:
                reward = -1.0
            else:
                reward = 0.0 # Draw
                
        return self._get_obs(), reward, terminated, False, {}

    def render(self):
        # Optional: could print the board in a simplified way
        pass
