"""
PeakBot — heuristic focused on peak-support control.

Strategy:
  1. Win immediately at peak if possible.
  2. Grab unoccupied peak supports (1,0,0), (0,1,0), (0,0,1) if reachable.
  3. Block opponent from reaching peak supports.
  4. Mandatory: pick random (forced).
  5. Otherwise: score by support counts (same as server's 'hard' AI) + peak support bonus.
"""

import random
from .base import BaseBot
from cubicup_game import (
    str_to_pos, pos_to_str, opponent,
    PEAK, PEAK_SUPPORTS,
)

PEAK_STR     = pos_to_str(PEAK)
PEAK_SUP_STR = {pos_to_str(s) for s in PEAK_SUPPORTS}


def _count_new_cups(board, pos_str, color):
    x, y, z = (int(v) for v in pos_str.split(','))
    board[pos_str] = color
    count = 0
    for cx, cy, cz in ((x-1, y, z), (x, y-1, z), (x, y, z-1)):
        if cx < 0 or cy < 0 or cz < 0:
            continue
        ck = f'{cx},{cy},{cz}'
        if board.get(ck) is not None:
            continue
        if (board.get(f'{cx+1},{cy},{cz}') == color and
                board.get(f'{cx},{cy+1},{cz}') == color and
                board.get(f'{cx},{cy},{cz+1}') == color):
            count += 1
    board[pos_str] = None
    return count


class PeakBot(BaseBot):
    """Prioritises controlling the three peak-support positions."""

    def choose_move(self, state):
        legal    = state['legal_moves']
        my_color = state['current_player']
        opp      = opponent(my_color)
        board    = state['board']

        # 1. Instant win at peak
        if PEAK_STR in legal:
            opp_sup = sum(1 for s in PEAK_SUP_STR if board.get(s) == opp)
            if opp_sup < 3:
                return PEAK_STR

        # 2 & 3. Peak support grabs
        open_supports = [m for m in legal if m in PEAK_SUP_STR and board.get(m) is None]
        if open_supports:
            return random.choice(open_supports)

        # 4. Mandatory — small look-ahead: prefer positions that don't give opponent cups
        if state['mandatory']:
            return random.choice(legal)

        # 5. Score by cups created/blocked + peak support owned
        my_sup  = sum(1 for s in PEAK_SUP_STR if board.get(s) == my_color)
        opp_sup = sum(1 for s in PEAK_SUP_STR if board.get(s) == opp)

        best_score = None
        best_moves = []
        for move_str in legal:
            own = _count_new_cups(board, move_str, my_color)
            blk = _count_new_cups(board, move_str, opp)
            score = own * 2 + blk
            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move_str]
            elif score == best_score:
                best_moves.append(move_str)

        return random.choice(best_moves)
