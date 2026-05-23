#!/usr/bin/env python3
"""
bot_runner.py — stdin/stdout bridge between server.js and the Python bots.

server.js spawns this for each AI move, writes JSON to stdin, reads JSON from stdout.

Input  (stdin):  { "difficulty": "greedy|peak|mcts|guided", "state": { ...state dict... } }
Output (stdout): { "move": "x,y,z" }

IMPORTANT: We pre-populate sys.modules['bots'] manually so that bots/__init__.py is
never executed — this avoids the slow RLBot / TensorFlow import on every call.
"""
import json
import sys
import os
import types

# ── Skip bots/__init__.py (avoids TensorFlow import from rl_bot) ─────────────
_bots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bots')
_bots_pkg = types.ModuleType('bots')
_bots_pkg.__path__    = [_bots_dir]
_bots_pkg.__package__ = 'bots'
_bots_pkg.__file__    = os.path.join(_bots_dir, '__init__.py')
sys.modules['bots']   = _bots_pkg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ─────────────────────────────────────────────────────────────────────────────

from bots.greedy_bot      import GreedyBot
from bots.peak_bot        import PeakBot
from bots.mcts_bot        import MCTSBot
from bots.guided_mcts_bot import GuidedMCTSBot

BOT_MAP = {
    'greedy': GreedyBot,
    'peak':   PeakBot,
    'mcts':   MCTSBot,
    'guided': GuidedMCTSBot,
}

def main():
    try:
        raw  = sys.stdin.buffer.read()           # binary read avoids BOM / encoding issues
        data = json.loads(raw.decode('utf-8-sig')) # utf-8-sig strips BOM if present

        difficulty = data.get('difficulty', 'greedy')
        state      = data['state']

        BotClass = BOT_MAP.get(difficulty, GreedyBot)
        bot      = BotClass()

        result = bot.choose_move(state)
        move   = result[0] if isinstance(result, (list, tuple)) else result

        print(json.dumps({'move': move}), flush=True)

    except Exception as e:
        print(json.dumps({'error': str(e)}), flush=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
