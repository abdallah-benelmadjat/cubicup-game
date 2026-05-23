"""
GuidedMCTSBot — MCTS with heuristic rollouts instead of random.

Same UCB1 tree as MCTSBot, but during simulation the playout policy
scores every candidate move and picks from the top tier rather than
uniformly at random.  This dramatically reduces rollout noise because
the simulations start resembling real play.

Rollout priority (same time budget as the original MCTSBot: 1 s):
  1. Instant win at peak.
  2. Mandatory fills chosen to maximise cups we'll create next (greedy).
  3. Normal moves scored by: cups_created*2 + cups_blocked + peak_support_bonus.
     Ties broken randomly so exploration isn't fully eliminated.
"""

import math
import random
import time

from .base import BaseBot
from cubicup_game import (
    str_to_pos, pos_to_str, apply_move, get_legal_moves,
    PEAK, PEAK_SUPPORTS, opponent, count_new_cups,
)

PEAK_STR = pos_to_str(PEAK)
C_UCB    = 1.41


class _Node:
    __slots__ = ('state', 'move', 'parent', 'children',
                 'wins', 'visits', 'untried', 'my_color')

    def __init__(self, state, move, parent, my_color):
        self.state    = state
        self.move     = move
        self.parent   = parent
        self.children = []
        self.wins     = 0.0
        self.visits   = 0
        self.my_color = my_color
        self.untried  = [pos_to_str(p) for p in get_legal_moves(state)]
        random.shuffle(self.untried)

    def ucb(self):
        if self.visits == 0:
            return float('inf')
        return (self.wins / self.visits +
                C_UCB * math.sqrt(math.log(self.parent.visits) / self.visits))

    def best_child(self):
        return max(self.children, key=lambda c: c.ucb())

    def is_terminal(self):
        return bool(self.state['terminal'])

    def is_fully_expanded(self):
        return not self.untried


def _heuristic_move(state, my_color):
    """Pick a move using greedy heuristics (not pure random)."""
    legal = get_legal_moves(state)
    if not legal:
        return None

    current = state['current_player']
    opp     = opponent(current)
    board   = state['board']

    # Instant win at peak
    if PEAK in legal:
        opp_sup = sum(1 for s in PEAK_SUPPORTS if board.get(s) == opp)
        if opp_sup < 3:
            return PEAK

    # Mandatory: pick the fill that gives the opponent the fewest cups
    if state['mandatory']:
        return min(legal, key=lambda p: count_new_cups(board, p, opp))

    # Score every move; sample from the best tier
    best_score = -1
    best       = []
    for pos in legal:
        own  = count_new_cups(board, pos, current)
        blk  = count_new_cups(board, pos, opp)
        psup = 2 if pos in PEAK_SUPPORTS and board.get(pos) is None else 0
        sc   = own * 2 + blk + psup
        if sc > best_score:
            best_score = sc
            best       = [pos]
        elif sc == best_score:
            best.append(pos)

    return random.choice(best)


def _guided_playout(state, my_color):
    for _ in range(300):
        if state['terminal']:
            break
        move = _heuristic_move(state, my_color)
        if move is None:
            break
        state = apply_move(state, move)

    result = state['terminal']
    if result == my_color: return 1.0
    if result == 'draw':   return 0.5
    if result is None:     return 0.5
    return 0.0


class GuidedMCTSBot(BaseBot):
    """MCTS with greedy-heuristic rollouts (1 s per move)."""

    def __init__(self, time_limit=1.0):
        self._time_limit = time_limit

    @property
    def name(self):
        return f'GuidedMCTSBot({self._time_limit:.1f}s)'

    def choose_move(self, state):
        my_color = state['current_player']
        legal    = state['legal_moves']

        if len(legal) == 1:
            return legal[0]

        # Instant win
        if PEAK_STR in legal:
            opp     = opponent(my_color)
            opp_sup = sum(1 for s in PEAK_SUPPORTS
                          if state['board'].get(pos_to_str(s)) == opp)
            if opp_sup < 3:
                return PEAK_STR

        players = list(state['cubes_left'].keys())
        internal = {
            'n':              state.get('n', 6),
            'all_players':    players,
            'board':          {str_to_pos(k): v for k, v in state['board'].items()},
            'current_player': state['current_player'],
            'mandatory':      tuple(str_to_pos(m) for m in state['mandatory']),
            'cubes_left':     dict(state['cubes_left']),
            'terminal':       state['terminal'],
            'move_history':   (),
        }

        root     = _Node(internal, None, None, my_color)
        deadline = time.time() + self._time_limit

        while time.time() < deadline:
            node = root

            # Selection
            while not node.is_terminal() and node.is_fully_expanded():
                node = node.best_child()

            # Expansion
            if not node.is_terminal() and node.untried:
                move_str  = node.untried.pop()
                new_state = apply_move(node.state, str_to_pos(move_str))
                child     = _Node(new_state, move_str, node, my_color)
                node.children.append(child)
                node = child

            # Simulation (guided)
            result = _guided_playout(node.state, my_color)

            # Backprop
            n = node
            while n is not None:
                n.visits += 1
                n.wins   += result
                n = n.parent

        if not root.children:
            return random.choice(legal)
        best = max(root.children, key=lambda c: c.visits)
        return best.move
