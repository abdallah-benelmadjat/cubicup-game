import numpy as np
from rl_env import CubiCupEnv
from bots.random_bot import RandomBot

def test_env():
    print("Testing CubiCupEnv...")
    env = CubiCupEnv(opponent_bot=RandomBot())
    obs, info = env.reset()
    print(f"Initial observation shape: {obs.shape}")
    
    terminated = False
    truncated = False
    total_reward = 0
    steps = 0
    
    while not (terminated or truncated):
        mask = env.action_masks()
        legal_indices = np.where(mask)[0]
        
        if len(legal_indices) == 0:
            print("No legal moves!")
            break
            
        action = np.random.choice(legal_indices)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1
        
    print(f"Game finished in {steps} steps. Total reward: {total_reward}")
    print("Environment test passed!")

if __name__ == "__main__":
    test_env()
