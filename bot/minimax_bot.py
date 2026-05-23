"""
MinimaxBot — alpha-beta minimax, depth 4.

Evaluation:
  - Terminal win/loss/draw: ±10000 / 0
  - Peak support control: ±200 per support owned
  - Cup potential: positions where 2/3 supports are my color
  - Blocks opponent cup potential
"""

import random
from .base import BaseBot
from cubicup_game import (
    str_to_pos, pos_to_str, apply_move, get_legal_moves,
    PEAK, PEAK_SUPPORTS, opponent, ALL_POSITIONS,
)

WIN_SCORE  =  10_000
DRAW_SCORE =  0
LOSS_SCORE = -10_000
DEPTH      = 4
PEAK_STR   = pos_to_str(PEAK)


def _api_to_internal(state):
    """Convert the API state dict (string board keys) to internal format (tuple keys)."""
    return {
        'n':              6,
        'board':          {str_to_pos(k): v for k, v in state['board'].items()},
        'current_player': state['current_player'],
        'mandatory':      tuple(str_to_pos(m) for m in state['mandatory']),
        'cubes_left':     dict(state['cubes_left']),
        'terminal':       state['terminal'],
        'move_history':   (),
    }


def _evaluate(state, my_color):
    terminal = state['terminal']
    if terminal is not None:
        if terminal == my_color:  return WIN_SCORE
        if terminal == 'draw':    return DRAW_SCORE
        return LOSS_SCORE

    board = state['board']
    opp   = opponent(my_color)
    score = 0

    for s in PEAK_SUPPORTS:
        owner = board.get(s)
        if owner == my_color:  score += 200
        elif owner == opp:     score -= 200

    for pos in ALL_POSITIONS:
        if board[pos] is not None:
            continue
        x, y, z = pos
        sup = [board.get((x+1, y, z)), board.get((x, y+1, z)), board.get((x, y, z+1))]
        my_sup  = sup.count(my_color)
        opp_sup = sup.count(opp)
        if my_sup == 3:    score += 80
        elif my_sup == 2:  score += 20
        if opp_sup == 3:   score -= 80
        elif opp_sup == 2: score -= 20

    return score


def _alphabeta(state, depth, alpha, beta, my_color, maximising):
    legal = get_legal_moves(state)

    if state['terminal'] or depth == 0 or not legal:
        return _evaluate(state, my_color)

    if maximising:
        best = LOSS_SCORE - 1
        for pos in legal:
            child = apply_move(state, pos)
            is_max = child['current_player'] == my_color
            val = _alphabeta(child, depth - 1, alpha, beta, my_color, is_max)
            if val > best:
                best = val
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best
    else:
        best = WIN_SCORE + 1
        for pos in legal:
            child = apply_move(state, pos)
            is_max = child['current_player'] == my_color
            val = _alphabeta(child, depth - 1, alpha, beta, my_color, is_max)
            if val < best:
                best = val
            beta = min(beta, best)
            if alpha >= beta:
                break
        return best


class MinimaxBot(BaseBot):
    """Alpha-beta minimax, fixed depth."""

    def __init__(self, depth=DEPTH):
        self._depth = depth

    @property
    def name(self):
        return f'MinimaxBot(d{self._depth})'

    def choose_move(self, state):
        my_color = state['current_player']
        legal    = state['legal_moves']

        if len(legal) == 1:
            return legal[0]

        # Instant win at peak
        if PEAK_STR in legal:
            opp     = opponent(my_color)
            opp_sup = sum(1 for s in PEAK_SUPPORTS
                          if state['board'].get(pos_to_str(s)) == opp)
            if opp_sup < 3:
                return PEAK_STR

        internal = _api_to_internal(state)

        best_score = None
        best_moves = []

        # Move ordering: peak first, then mandatory, then rest
        ordered = sorted(legal, key=lambda m: (0 if m == PEAK_STR else
                                               (1 if state['mandatory'] else 2)))

        for move_str in ordered:
            pos   = str_to_pos(move_str)
            child = apply_move(internal, pos)
            is_max = child['current_player'] == my_color
            score = _alphabeta(child, self._depth - 1,
                                LOSS_SCORE, WIN_SCORE, my_color, is_max)

            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move_str]
            elif score == best_score:
                best_moves.append(move_str)

        chosen = random.choice(best_moves)
        debug = f"Best minimax score: {best_score}. Candidates: {', '.join(best_moves)}"
        return chosen, debug
