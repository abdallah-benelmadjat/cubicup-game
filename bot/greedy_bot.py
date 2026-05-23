"""
GreedyBot — one-ply lookahead.

Priority (descending):
  1. Win immediately (place at peak if it's a win, not a draw).
  2. Mandatory: pick the mandatory position that creates the most NEW cups for us.
  3. Maximize cups_created - cups_blocked in one move.
  4. Tie-break: peak support control, then random.
"""

import random
from .base import BaseBot
from cubicup_game import (
    str_to_pos, pos_to_str, apply_move, get_legal_moves,
    PEAK, PEAK_SUPPORTS, opponent,
)


def _count_new_cups(board, pos, color):
    """How many CubiCup positions does placing `color` at `pos` create?"""
    board[pos] = color
    x, y, z = pos
    count = 0
    for cx, cy, cz in ((x-1, y, z), (x, y-1, z), (x, y, z-1)):
        if cx < 0 or cy < 0 or cz < 0:
            continue
        p = (cx, cy, cz)
        if board.get(p) is not None:
            continue
        if (board.get((cx+1, cy, cz)) == color and
                board.get((cx, cy+1, cz)) == color and
                board.get((cx, cy, cz+1)) == color):
            count += 1
    board[pos] = None
    return count


class GreedyBot(BaseBot):

    def choose_move(self, state):
        legal    = state['legal_moves']
        my_color = state['current_player']
        opp      = opponent(my_color)
        board    = {(int(x), int(y), int(z)): v
                    for key, v in state['board'].items()
                    for x, y, z in [key.split(',')]}

        peak_str = pos_to_str(PEAK)

        # 1. Instant win at peak
        if peak_str in legal:
            opp_supports = sum(1 for s in PEAK_SUPPORTS if board.get(s) == opp)
            if opp_supports < 3:
                return peak_str

        # Score each move
        best_score = None
        best_moves = []

        for move_str in legal:
            pos   = str_to_pos(move_str)
            own   = _count_new_cups(board, pos, my_color)
            blk   = _count_new_cups(board, pos, opp)

            # Peak support bonus
            peak_bonus = 3 if pos in PEAK_SUPPORTS and board.get(pos) is None else 0

            score = own * 2 + blk + peak_bonus

            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move_str]
            elif score == best_score:
                best_moves.append(move_str)

        chosen = random.choice(best_moves)
        debug = {
            'reason': f'Maximized score ({best_score}) among {len(best_moves)} candidates.',
            'candidates': best_moves,
            'best_score': best_score
        }
        return chosen, debug
