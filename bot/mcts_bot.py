"""
MCTSBot — Monte Carlo Tree Search with UCB1.

Runs simulations for `time_limit` seconds per move.
Rollouts use a light playout policy: take instant wins, otherwise random.
"""

import math
import random
import time

from .base import BaseBot
from cubicup_game import (
    str_to_pos, pos_to_str, apply_move, get_legal_moves,
    PEAK, PEAK_SUPPORTS, opponent,
)

PEAK_STR = pos_to_str(PEAK)
C_UCB    = 1.41   # exploration constant


class _Node:
    __slots__ = ('state', 'move', 'parent', 'children',
                 'wins', 'visits', 'untried', 'my_color')

    def __init__(self, state, move, parent, my_color):
        self.state    = state
        self.move     = move       # move that led here (str), None for root
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
        exploit = self.wins / self.visits
        explore = C_UCB * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploit + explore

    def best_child(self):
        return max(self.children, key=lambda c: c.ucb())

    def is_terminal(self):
        return bool(self.state['terminal'])

    def is_fully_expanded(self):
        return not self.untried


def _light_playout(state, my_color):
    """Rollout: instant-win moves first, then random."""
    max_moves = 300
    for _ in range(max_moves):
        if state['terminal']:
            break
        legal = get_legal_moves(state)
        if not legal:
            break

        legal_str = [pos_to_str(p) for p in legal]

        # Take instant win at peak
        if PEAK_STR in legal_str:
            board = state['board']
            opp   = opponent(state['current_player'])
            opp_sup = sum(1 for s in PEAK_SUPPORTS if board.get(s) == opp)
            if opp_sup < 3:
                state = apply_move(state, PEAK)
                break

        state = apply_move(state, random.choice(legal))

    result = state['terminal']
    if result == my_color:   return 1.0
    if result == 'draw':     return 0.5
    if result is None:       return 0.5   # hit move limit → count as draw
    return 0.0


class MCTSBot(BaseBot):

    def __init__(self, time_limit=1.0):
        self._time_limit = time_limit

    @property
    def name(self):
        return f'MCTSBot({self._time_limit:.1f}s)'

    def choose_move(self, state):
        my_color = state['current_player']
        legal    = state['legal_moves']

        if len(legal) == 1:
            return legal[0]

        # Instant win
        if PEAK_STR in legal:
            board   = state['board']
            opp     = opponent(my_color)
            opp_sup = sum(1 for s in PEAK_SUPPORTS
                          if board.get(pos_to_str(s)) == opp)
            if opp_sup < 3:
                return PEAK_STR

        # Convert API state to internal state for MCTS tree
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

            # Simulation
            result = _light_playout(node.state, my_color)

            # Backprop
            n = node
            while n is not None:
                n.visits += 1
                n.wins   += result
                n = n.parent

        # Pick child with most visits
        if not root.children:
            return random.choice(legal)
        best = max(root.children, key=lambda c: c.visits)
        return best.move


class MCTSBot3(MCTSBot):
    """MCTSBot with a 3-second time budget per move."""

    def __init__(self):
        super().__init__(time_limit=3.0)

    @property
    def name(self):
        return 'MCTSBot(3.0s)'
