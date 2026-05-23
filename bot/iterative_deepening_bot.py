"""
IterativeDeepeningBot — time-limited iterative-deepening alpha-beta.

Runs alpha-beta at depth 1, 2, 3, ... until the time budget runs out,
then returns the best move found at the deepest completed depth.

Evaluation improvements over the original MinimaxBot:
  - Peak supports weighted 5x higher (they decide the game)
  - Explicit win-now detection when peak is legal
  - Mandatory chain tempo bonus
  - Cup potential scoring
"""

import random
import time

from .base import BaseBot
from cubicup_game import (
    str_to_pos, pos_to_str, apply_move, get_legal_moves,
    PEAK, PEAK_SUPPORTS, opponent, ALL_POSITIONS, count_new_cups,
)

WIN_SCORE  =  100_000
DRAW_SCORE =  0
LOSS_SCORE = -100_000
PEAK_STR   = pos_to_str(PEAK)
TIME_LIMIT = 1.0


class _Timeout(Exception):
    pass


def _evaluate(state, my_color):
    terminal = state['terminal']
    if terminal == my_color:  return WIN_SCORE
    if terminal == 'draw':    return DRAW_SCORE
    if terminal is not None:  return LOSS_SCORE

    board   = state['board']
    opp     = opponent(my_color)
    current = state['current_player']
    score   = 0

    # Peak availability — highest priority signal
    legal = get_legal_moves(state)
    if PEAK in legal:
        opp_sup = sum(1 for s in PEAK_SUPPORTS if board.get(s) == opp)
        my_sup  = sum(1 for s in PEAK_SUPPORTS if board.get(s) == my_color)
        if current == my_color:
            score += 5000 if opp_sup < 3 else 0    # I can win right now
        else:
            score -= 5000 if my_sup  < 3 else 0    # opponent can win right now

    # Peak support ownership
    for s in PEAK_SUPPORTS:
        owner = board.get(s)
        if owner == my_color:  score += 1000
        elif owner == opp:     score -= 1000

    # Mandatory tempo advantage
    if state['mandatory']:
        if current == opp:
            score += len(state['mandatory']) * 50
        else:
            score -= len(state['mandatory']) * 50

    # Cup potential
    for pos in ALL_POSITIONS:
        if board[pos] is not None:
            continue
        x, y, z = pos
        sup     = [board.get((x+1, y, z)), board.get((x, y+1, z)), board.get((x, y, z+1))]
        my_s    = sup.count(my_color)
        opp_s   = sup.count(opp)
        if my_s  == 3:  score += 150
        elif my_s  == 2: score += 30
        if opp_s == 3:  score -= 150
        elif opp_s == 2: score -= 30

    return score


def _move_order(state, legal, my_color):
    """Peak first, then moves that create cups, then rest."""
    opp = opponent(my_color)

    def _priority(pos):
        if pos == PEAK:
            return 0
        if state['mandatory']:
            return 1
        own = count_new_cups(state['board'], pos, my_color)
        blk = count_new_cups(state['board'], pos, opp)
        return -(own * 2 + blk)   # negative so higher scores sort first

    return sorted(legal, key=_priority)


def _alphabeta(state, depth, alpha, beta, my_color, maximising, deadline):
    if time.time() > deadline:
        raise _Timeout()

    legal = get_legal_moves(state)

    if state['terminal'] or depth == 0 or not legal:
        return _evaluate(state, my_color), None

    ordered = _move_order(state, legal, my_color)
    best_move = ordered[0]

    if maximising:
        best_val = LOSS_SCORE - 1
        for pos in ordered:
            child = apply_move(state, pos)
            is_max = child['current_player'] == my_color
            val, _ = _alphabeta(child, depth - 1, alpha, beta, my_color, is_max, deadline)
            if val > best_val:
                best_val  = val
                best_move = pos
            alpha = max(alpha, best_val)
            if alpha >= beta:
                break
        return best_val, best_move
    else:
        best_val = WIN_SCORE + 1
        for pos in ordered:
            child = apply_move(state, pos)
            is_max = child['current_player'] == my_color
            val, _ = _alphabeta(child, depth - 1, alpha, beta, my_color, is_max, deadline)
            if val < best_val:
                best_val  = val
                best_move = pos
            beta = min(beta, best_val)
            if alpha >= beta:
                break
        return best_val, best_move


def _api_to_internal(state):
    return {
        'board':          {str_to_pos(k): v for k, v in state['board'].items()},
        'current_player': state['current_player'],
        'mandatory':      tuple(str_to_pos(m) for m in state['mandatory']),
        'cubes_left':     dict(state['cubes_left']),
        'terminal':       state['terminal'],
        'move_history':   (),
    }


class IterativeDeepeningBot(BaseBot):
    """Time-limited iterative-deepening alpha-beta (1 s budget)."""

    def __init__(self, time_limit=TIME_LIMIT):
        self._time_limit = time_limit

    @property
    def name(self):
        return 'IterDeepBot'

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

        internal = _api_to_internal(state)
        deadline = time.time() + self._time_limit
        is_max   = internal['current_player'] == my_color

        best_move = str_to_pos(legal[0])
        depth     = 1

        while True:
            try:
                val, move = _alphabeta(
                    internal, depth, LOSS_SCORE, WIN_SCORE, my_color, is_max, deadline
                )
                if move is not None:
                    best_move = move
                if val >= WIN_SCORE:   # proven win found
                    break
                depth += 1
            except _Timeout:
                break

        return pos_to_str(best_move)
