"""
cubicup_game.py — Pure-Python CubiCup game engine (ported from server.js).

Positions are (x, y, z) tuples internally.
The pyramid has N=6 layers; valid positions satisfy x+y+z <= N-1.
The peak is (0,0,0); the base layer satisfies x+y+z == N-1.

A position is playable if it is empty AND either:
  - it is on the base layer (x+y+z == 5), OR
  - all three positions above it are occupied: (x+1,y,z), (x,y+1,z), (x,y,z+1)

A CubiCup forms at empty playable position (cx,cy,cz) when:
  board[cx+1,cy,cz] == board[cx,cy+1,cz] == board[cx,cy,cz+1] == same color

Mandatory rule: when a player creates CubiCup(s), the OPPONENT must fill all of
them before the turn passes again (one mandatory fill per sub-turn).

Peak rule: placing at (0,0,0) ends the game.
  - If all three peak supports [(1,0,0),(0,1,0),(0,0,1)] are opponent's color → DRAW
  - Otherwise → current player WINS
"""

N = 6
YELLOW = 'yellow'
BLUE = 'blue'
PEAK = (0, 0, 0)
PEAK_SUPPORTS = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

def get_all_positions(n):
    return tuple(
        (x, y, z)
        for x in range(n) for y in range(n) for z in range(n)
        if x + y + z <= n - 1
    )

ALL_POSITIONS = get_all_positions(N)

def count_new_cups(board, pos, color):
    """How many CubiCup positions does placing `color` at `pos` create?
    Assumes pos is currently empty.
    """
    x, y, z = pos
    # Temporarily place the cube
    board[pos] = color
    count = 0
    # A cube at (x,y,z) can complete cups at (x-1,y,z), (x,y-1,z), (x,y,z-1)
    for cx, cy, cz in ((x-1, y, z), (x, y-1, z), (x, y, z-1)):
        if cx < 0 or cy < 0 or cz < 0:
            continue
        cp = (cx, cy, cz)
        # The cup position itself must be empty
        if board.get(cp) is not None:
            continue
        # Check if all 3 supports of the potential cup are now the same color
        if (board.get((cx+1, cy, cz)) == color and
            board.get((cx, cy+1, cz)) == color and
            board.get((cx, cy, cz+1)) == color):
            count += 1
    # Clean up
    board[pos] = None
    return count

def opponent(color, all_players=(YELLOW, BLUE)):
    """Next player in the rotation."""
    idx = all_players.index(color)
    return all_players[(idx + 1) % len(all_players)]

def fresh_board(n):
    return {pos: None for pos in get_all_positions(n)}

def is_valid_move(board, pos, n):
    if board.get(pos) is not None:
        return False
    x, y, z = pos
    if x + y + z == n - 1:
        return True
    return (board.get((x+1, y, z)) is not None and
            board.get((x, y+1, z)) is not None and
            board.get((x, y, z+1)) is not None)

def get_valid_moves(board, n):
    return [p for p in get_all_positions(n) if is_valid_move(board, p, n)]

def get_cubicups(board, color, n):
    """Positions that are valid (empty+supported) AND all 3 supports are `color`."""
    result = []
    for pos in get_all_positions(n):
        if board.get(pos) is not None:
            continue
        x, y, z = pos
        if (board.get((x+1, y, z)) == color and
                board.get((x, y+1, z)) == color and
                board.get((x, y, z+1)) == color):
            result.append(pos)
    return result

def get_legal_moves(state):
    if state['terminal']:
        return []
    if state['mandatory']:
        return list(state['mandatory'])
    return get_valid_moves(state['board'], state['n'])

def apply_move(state, pos):
    n           = state['n']
    board       = dict(state['board'])
    current     = state['current_player']
    all_players = state['all_players']
    board[pos]  = current
    cubes       = dict(state['cubes_left'])
    cubes[current] -= 1
    history     = state['move_history'] + (pos,)

    peak = (0, 0, 0)
    if pos == peak:
        # For multiple players, it's a draw if ALL supports are NOT the current player?
        # Standard rule: draw if all three supports are opponent's color.
        # In multi-player: draw if all three supports are the SAME color (other than current)?
        # Let's stick to the spirit: draw if the move completes a cup for SOMEONE ELSE.
        other_colors = [c for c in all_players if c != current]
        is_draw = False
        for oc in other_colors:
            supp_count = sum(1 for s in [(1,0,0), (0,1,0), (0,0,1)] if board.get(s) == oc)
            if supp_count == 3:
                is_draw = True
                break

        return {
            'n':              n,
            'all_players':    all_players,
            'board':          board,
            'current_player': current,
            'mandatory':      (),
            'cubes_left':     cubes,
            'terminal':       'draw' if is_draw else current,
            'move_history':   history,
        }

    was_mandatory = bool(state['mandatory'])
    if was_mandatory:
        new_mandatory = tuple(k for k in state['mandatory'] if k != pos)
        new_player    = current
    else:
        new_mandatory = tuple(get_cubicups(board, current, n))
        new_player    = opponent(current, all_players)

    # Skip players with no cubes
    attempts = 0
    while cubes[new_player] == 0 and attempts < len(all_players):
        new_mandatory = () # Clear mandatory if skipping
        new_player = opponent(new_player, all_players)
        attempts += 1

    if cubes[new_player] == 0: # Everyone out
        # Determine winner by most cups? Or just draw?
        # Original logic implies game ends at peak. If everyone runs out before peak, it's a draw.
        return {
            'n':              n,
            'all_players':    all_players,
            'board':          board,
            'current_player': current,
            'mandatory':      (),
            'cubes_left':     cubes,
            'terminal':       'draw',
            'move_history':   history,
        }

    return {
        'n':              n,
        'all_players':    all_players,
        'board':          board,
        'current_player': new_player,
        'mandatory':      new_mandatory,
        'cubes_left':     cubes,
        'terminal':       None,
        'move_history':   history,
    }

def fresh_state(n=6, players=('yellow', 'blue')):
    # Calculate starting cubes: for N=6, it's 28 for 2 players.
    # Total positions for N=6 is 56.
    # General formula for tetrahedral number: n(n+1)(n+2)/6
    total_pos = n * (n + 1) * (n + 2) // 6
    cubes_per_player = total_pos // len(players)
    remainder = total_pos % len(players)

    cubes_left = {}
    for i, p in enumerate(players):
        # Distribute remainder cubes to the first players
        count = cubes_per_player + (1 if i < remainder else 0)
        cubes_left[p] = count

    return {
        'n':              n,
        'all_players':    players,
        'board':          fresh_board(n),
        'current_player': players[0],
        'mandatory':      (),
        'cubes_left':     cubes_left,
        'terminal':       None,
        'move_history':   (),
    }



# ── Helpers for interop with the Socket.IO API (string keys) ─────────────────

def pos_to_str(pos):
    return f'{pos[0]},{pos[1]},{pos[2]}'

def str_to_pos(s):
    x, y, z = s.split(',')
    return (int(x), int(y), int(z))

def state_to_api(state, my_color=None):
    """Convert internal state to the same dict the server sends to bots."""
    board_str = {pos_to_str(k): v for k, v in state['board'].items()}
    legal      = [pos_to_str(p) for p in get_legal_moves(state)]
    return {
        'board':          board_str,
        'current_player': state['current_player'],
        'your_turn':      (state['current_player'] == my_color) if my_color else None,
        'mandatory':      [pos_to_str(p) for p in state['mandatory']],
        'cubes_left':     dict(state['cubes_left']),
        'legal_moves':    legal,
        'move_number':    len(state['move_history']),
        'terminal':       state['terminal'],
    }


def play_game(bot_yellow, bot_blue, move_limit=300):
    """
    Run a full game between two bots.
    Returns a dict containing:
      winner: 'yellow'|'blue'|'draw'
      history: list of {move, player, debug_info}
      names: {yellow: name, blue: name}
    """
    state = fresh_state()
    bots  = {YELLOW: bot_yellow, BLUE: bot_blue}
    history = []

    for _ in range(move_limit):
        if state['terminal']:
            return {
                'winner': state['terminal'],
                'history': history,
                'names': {YELLOW: bot_yellow.name, BLUE: bot_blue.name}
            }

        current = state['current_player']
        bot     = bots[current]
        api     = state_to_api(state, current)

        result = bot.choose_move(api)
        debug_info = None
        if isinstance(result, (tuple, list)):
            move_str, debug_info = result
        else:
            move_str = result

        if move_str not in api['legal_moves']:
            raise ValueError(
                f'{bot.name} played illegal move "{move_str}". '
                f'Legal: {api["legal_moves"][:5]}...'
            )

        history.append({
            'move': move_str,
            'player': current,
            'debug': debug_info,
            'move_number': len(history) + 1
        })

        state = apply_move(state, str_to_pos(move_str))

    raise RuntimeError(f'Game exceeded {move_limit} moves without finishing.')
