import os
import gymnasium as gym
import torch
import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from rl_env import CubiCupEnv
from bots.random_bot import RandomBot
from bots.greedy_bot import GreedyBot
from bots.peak_bot import PeakBot
from bots.mcts_bot import MCTSBot
from bots.guided_mcts_bot import GuidedMCTSBot

# Create models directory
os.makedirs("models", exist_ok=True)

def mask_fn(env: gym.Env) -> np.ndarray:
    return env.unwrapped.action_masks()

def make_env(opponent_bot):
    env = CubiCupEnv(opponent_bot=opponent_bot)
    env = ActionMasker(env, mask_fn)
    return env

def train():
    # Stage 1: RandomBot (ELO 959)
    print("--- Stage 1: Training against RandomBot ---")
    env = make_env(RandomBot())
    model = MaskablePPO("MlpPolicy", env, verbose=1, tensorboard_log="./ppo_cubi_tensorboard/")
    model.learn(total_timesteps=50000)
    model.save("models/ppo_cubicup_stage1")
    
    # Stage 2: GreedyBot (ELO 1338)
    print("\n--- Stage 2: Training against GreedyBot ---")
    env = make_env(GreedyBot())
    model.set_env(env)
    model.learn(total_timesteps=100000)
    model.save("models/ppo_cubicup_stage2")

    # Stage 3: PeakBot (ELO 1313 - actually slightly lower but good for specific tactics)
    print("\n--- Stage 3: Training against PeakBot ---")
    env = make_env(PeakBot())
    model.set_env(env)
    model.learn(total_timesteps=100000)
    model.save("models/ppo_cubicup_stage3")
    
    # Stage 4: MCTSBot (ELO 1384)
    # Reduced time limit to 0.1s for training throughput
    print("\n--- Stage 4: Training against MCTSBot (0.1s) ---")
    env = make_env(MCTSBot(time_limit=0.1))
    model.set_env(env)
    model.learn(total_timesteps=150000)
    model.save("models/ppo_cubicup_stage4")

    # Stage 5: GuidedMCTSBot (The Undisputed Champion)
    # Reduced time limit to 0.1s for training throughput
    print("\n--- Stage 5: Training against GuidedMCTSBot (0.1s) ---")
    env = make_env(GuidedMCTSBot(time_limit=0.1))
    model.set_env(env)
    model.learn(total_timesteps=200000)
    model.save("models/ppo_cubicup_final")
    
    print("\nTraining complete. Final model saved to models/ppo_cubicup_final")

if __name__ == "__main__":
    train()
