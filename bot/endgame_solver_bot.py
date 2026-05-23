"""
EndgameSolverBot — perfect play once the peak enters the legal-move set.

Phase 1 (peak not yet legal): uses MandatoryChainBot heuristic.
Phase 2 (peak is legal): switches to exact minimax — no depth limit,
  searches every line until the game ends.  Because the peak becomes
  legal only when its three supports are filled, the number of positions
  still empty at that point is bounded, making the search fast.

If the endgame search exceeds the time budget (default 5 s) it falls
back to a greedy pick: take the peak if it's a win, otherwise grab a
peak support if available, otherwise greedy.
"""

import random
import time

from .base import BaseBot
from cubicup_game import (
    str_to_pos, pos_to_str, apply_move, get_legal_moves,
    PEAK, PEAK_SUPPORTS, opponent, ALL_POSITIONS, count_new_cups,
)

PEAK_STR  = pos_to_str(PEAK)
WIN_SCORE =  1_000_000
LOSS_SCORE = -1_000_000
DRAW_SCORE = 0


# ── Endgame exact solver ────────────────────────────────────────────────────

class _Timeout(Exception):
    pass


def _minimax_exact(state, alpha, beta, my_color, maximising, deadline):
    if time.time() > deadline:
        raise _Timeout()

    terminal = state['terminal']
    if terminal is not None:
        if terminal == my_color: return WIN_SCORE, None
        if terminal == 'draw':   return DRAW_SCORE, None
        return LOSS_SCORE, None

    legal = get_legal_moves(state)
    if not legal:
        return DRAW_SCORE, None   # shouldn't happen in normal play

    # Move ordering: peak first
    ordered = sorted(legal, key=lambda p: 0 if p == PEAK else 1)
    best_move = ordered[0]

    if maximising:
        best = LOSS_SCORE - 1
        for pos in ordered:
            child = apply_move(state, pos)
            is_max = child['current_player'] == my_color
            val, _ = _minimax_exact(child, alpha, beta, my_color, is_max, deadline)
            if val > best:
                best      = val
                best_move = pos
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best, best_move
    else:
        best = WIN_SCORE + 1
        for pos in ordered:
            child = apply_move(state, pos)
            is_max = child['current_player'] == my_color
            val, _ = _minimax_exact(child, alpha, beta, my_color, is_max, deadline)
            if val < best:
                best      = val
                best_move = pos
            beta = min(beta, best)
            if alpha >= beta:
                break
        return best, best_move


# ── Midgame heuristic (MandatoryChain logic inlined) ───────────────────────

def _evaluate_mid(state, my_color):
    board = state['board']
    opp   = opponent(my_color)
    score = 0
    for s in PEAK_SUPPORTS:
        owner = board.get(s)
        if owner == my_color:  score += 800
        elif owner == opp:     score -= 800
    for pos in ALL_POSITIONS:
        if board[pos] is not None:
            continue
        x, y, z = pos
        sup   = [board.get((x+1, y, z)), board.get((x, y+1, z)), board.get((x, y, z+1))]
        my_s  = sup.count(my_color)
        opp_s = sup.count(opp)
        if my_s  == 3:  score += 120
        elif my_s  == 2: score += 25
        if opp_s == 3:  score -= 120
        elif opp_s == 2: score -= 25
    return score


def _resolve_chain(state, my_color):
    opp = opponent(my_color)
    while state['mandatory'] and not state['terminal']:
        best_pos = min(
            state['mandatory'],
            key=lambda p: count_new_cups(state['board'], p, my_color)
        )
        state = apply_move(state, best_pos)
    return state


def _midgame_move(internal, my_color, legal):
    """MandatoryChain heuristic for the midgame phase."""
    opp = opponent(my_color)
    best_score = None
    best_moves = []
    for pos in legal:
        after = _resolve_chain(apply_move(internal, pos), my_color)
        score = _evaluate_mid(after, my_color)
        if best_score is None or score > best_score:
            best_score = score
            best_moves = [pos]
        elif score == best_score:
            best_moves.append(pos)
    return random.choice(best_moves)


def _api_to_internal(state):
    return {
        'board':          {str_to_pos(k): v for k, v in state['board'].items()},
        'current_player': state['current_player'],
        'mandatory':      tuple(str_to_pos(m) for m in state['mandatory']),
        'cubes_left':     dict(state['cubes_left']),
        'terminal':       state['terminal'],
        'move_history':   (),
    }


# ── Bot ─────────────────────────────────────────────────────────────────────

class EndgameSolverBot(BaseBot):
    """
    Heuristic midgame + exact minimax once the peak becomes reachable.
    """

    def __init__(self, endgame_time=5.0):
        self._endgame_time = endgame_time

    @property
    def name(self):
        return 'EndgameSolverBot'

    def choose_move(self, state):
        my_color  = state['current_player']
        legal_str = state['legal_moves']
        opp       = opponent(my_color)

        if len(legal_str) == 1:
            return legal_str[0]

        # Always take a winning peak immediately
        if PEAK_STR in legal_str:
            opp_sup = sum(1 for s in PEAK_SUPPORTS
                          if state['board'].get(pos_to_str(s)) == opp)
            if opp_sup < 3:
                return PEAK_STR

        internal = _api_to_internal(state)
        legal    = get_legal_moves(internal)
        is_max   = internal['current_player'] == my_color

        # Phase 2: peak is legal — run exact solver
        if PEAK in legal:
            deadline = time.time() + self._endgame_time
            try:
                val, move = _minimax_exact(
                    internal, LOSS_SCORE, WIN_SCORE, my_color, is_max, deadline
                )
                if move is not None:
                    return pos_to_str(move)
            except _Timeout:
                pass   # fallthrough to heuristic

        # Phase 1 (or endgame timeout fallback): MandatoryChain heuristic
        move = _midgame_move(internal, my_color, legal)
        return pos_to_str(move)
