"""
MandatoryChainBot — exploits the mandatory-fill rule as a tempo weapon.

Core idea: when a normal move creates K cup positions, the opponent must
spend K sub-turns filling them (they don't get to do anything else).
Those K sub-turns are "tempo" we gain.  This bot searches for moves that
maximise tempo gained while minimising tempo conceded, then evaluates the
board position AFTER the full mandatory chain resolves.

Algorithm (1.5-ply lookahead):
  For each legal move M:
    1. Apply M.
    2. Resolve the mandatory chain: opponent fills each mandatory position
       in the order that minimises the cups they create (worst case for us).
       Since mandatory fills cannot themselves create new mandatory positions,
       this loop always terminates.
    3. Evaluate the resulting post-chain board with a peak-focused heuristic.
  Pick the M with the best post-chain evaluation.

Why mandatory fills don't cascade: the JS/game engine only checks for new
CubiCups on NORMAL (non-mandatory) moves.  Mandatory fills shrink the list
but never extend it.
"""

import random

from .base import BaseBot
from cubicup_game import (
    str_to_pos, pos_to_str, apply_move, get_legal_moves,
    PEAK, PEAK_SUPPORTS, opponent, ALL_POSITIONS, count_new_cups,
)

PEAK_STR = pos_to_str(PEAK)
WIN      =  1_000_000
DRAW     =  0
LOSS     = -1_000_000


def _evaluate_post_chain(state, my_color):
    """Static eval used AFTER mandatory chain is resolved."""
    terminal = state['terminal']
    if terminal == my_color:  return WIN
    if terminal == 'draw':    return DRAW
    if terminal is not None:  return LOSS

    board = state['board']
    opp   = opponent(my_color)
    score = 0

    # Peak control — the decisive factor
    for s in PEAK_SUPPORTS:
        owner = board.get(s)
        if owner == my_color:  score += 800
        elif owner == opp:     score -= 800

    # If peak is already legal, huge bonus/penalty
    if board.get(PEAK) is None:
        x, y, z = PEAK
        if (board.get((x+1, y, z)) is not None and
                board.get((x, y+1, z)) is not None and
                board.get((x, y, z+1)) is not None):
            opp_sup = sum(1 for s in PEAK_SUPPORTS if board.get(s) == opp)
            my_sup  = sum(1 for s in PEAK_SUPPORTS if board.get(s) == my_color)
            if state['current_player'] == my_color:
                score += 4000 if opp_sup < 3 else 0
            else:
                score -= 4000 if my_sup < 3 else 0

    # Cup potential
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
    """
    Fast-forward through mandatory fills.
    Opponent (filling our created cups) picks the mandatory position
    that minimises the cups they'd create for us — i.e. worst for us.
    Since mandatory fills never create new mandatory positions, this loop
    is bounded by the initial mandatory length.
    """
    opp = opponent(my_color)
    while state['mandatory'] and not state['terminal']:
        # Opponent picks mandatory fill to minimise our future cups
        best_pos  = min(
            state['mandatory'],
            key=lambda p: count_new_cups(state['board'], p, my_color)
        )
        state = apply_move(state, best_pos)
    return state


def _api_to_internal(state):
    return {
        'board':          {str_to_pos(k): v for k, v in state['board'].items()},
        'current_player': state['current_player'],
        'mandatory':      tuple(str_to_pos(m) for m in state['mandatory']),
        'cubes_left':     dict(state['cubes_left']),
        'terminal':       state['terminal'],
        'move_history':   (),
    }


class MandatoryChainBot(BaseBot):
    """
    Picks moves that maximise positional advantage after mandatory chains resolve.
    """

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

        for move_str in legal:
            pos         = str_to_pos(move_str)
            after_move  = apply_move(internal, pos)
            after_chain = _resolve_chain(after_move, my_color)
            score       = _evaluate_post_chain(after_chain, my_color)

            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move_str]
            elif score == best_score:
                best_moves.append(move_str)

        return random.choice(best_moves)
