# CubiCup AI: Reinforcement Learning & Tree Search

A comprehensive implementation of the CubiCup board game featuring a hierarchy of AI bots, ranging from simple heuristics to state-of-the-art **Reinforcement Learning** and **Monte Carlo Tree Search**.

## 🚀 Features
- **Maskable PPO RL Agent:** A Reinforcement Learning model trained via curriculum learning that respects 3D game constraints through action masking.
- **Monte Carlo Tree Search (MCTS):** High-performance bots using UCB1 and guided heuristic rollouts.
- **Curriculum Training Pipeline:** Automated training script that evolves the RL agent through 5 stages of difficulty.
- **Gymnasium Environment:** A fully compatible `gym` environment for the CubiCup game logic.

## 🎮 Game Modes
### 1. Standard (6 Layers, 2 Players)
The classic CubiCup experience against AI or another human.

### 2. Death Match (Custom Layers & Players)
Play locally with any number of players and a custom pyramid size. The cube counts scale automatically to ensure a perfect pyramid.
```bash
python death_match.py
```

## 🤖 Bot Difficulties
| Difficulty | Bot Name | Logic Type |
| :--- | :--- | :--- |
| **Easy** | `RandomBot` | Uniform Random |
| **Medium** | `GreedyBot` | 1-Ply Heuristic (Cup maximization) |
| **Medium-Hard** | `PeakBot` | Positional control (Peak-focused) |
| **Hard** | `MCTSBot` | Monte Carlo Tree Search (1.0s) |
| **Extreme** | `GuidedMCTSBot` | Heuristic-guided MCTS (The Champion) |
| **Elite** | `RLBot` | Trained Maskable PPO Model |

## 🛠️ Setup & Installation
1. Install dependencies:
   ```bash
   pip install gymnasium stable-baselines3 sb3-contrib torch numpy tensorboard
   ```
2. (Optional) Run the environment smoke test:
   ```bash
   python test_env.py
   ```

## 🏋️ Training the RL Model
The model uses **Curriculum Learning** to master the game:
```bash
python train_rl.py
```
To monitor progress in real-time with graphs:
```bash
python -m tensorboard.main --logdir ./ppo_cubi_tensorboard/
```

## 📊 Tournament Evaluation
Compare all bots and your trained RL agent:
```bash
python tournament.py
```

## 📂 Project Structure
- `rl_env.py`: The Gymnasium environment wrapper.
- `train_rl.py`: Stage-based training orchestration.
- `bots/`: Directory containing all bot implementations.
- `cubicup_game.py`: The core CubiCup engine (Python port).
