"""
death_match.py — Local Multiplayer CubiCup with custom layers and players.
"""

import sys
from cubicup_game import fresh_state, apply_move, get_legal_moves, str_to_pos, pos_to_str

def run_death_match():
    print("=== Welcome to CubiCup DEATH MATCH ===")
    
    try:
        layers = int(input("Enter number of layers (default 6): ") or 6)
        num_players = int(input("Enter number of players (2-6, default 2): ") or 2)
    except ValueError:
        print("Invalid input. Using defaults.")
        layers = 6
        num_players = 2

    colors = ["yellow", "blue", "red", "green", "purple", "orange"]
    player_names = colors[:num_players]
    
    state = fresh_state(n=layers, players=player_names)
    
    print(f"\nGame started with {layers} layers and {num_players} players.")
    for p, count in state['cubes_left'].items():
        print(f"  - Player {p}: {count} cubes")

    while not state['terminal']:
        current = state['current_player']
        legal = get_legal_moves(state)
        
        print(f"\n--- Player {current.upper()}'s Turn ---")
        print(f"Cubes left: {state['cubes_left'][current]}")
        
        if state['mandatory']:
            print(f"MANDATORY FILL REQUIRED at: {', '.join(map(pos_to_str, state['mandatory']))}")
        
        print(f"Sample Legal Moves: {', '.join(map(pos_to_str, legal[:10]))}...")
        
        move_input = input(f"Enter move (x,y,z): ").strip()
        
        try:
            move_pos = str_to_pos(move_input)
            if move_pos not in legal:
                print("Illegal move! Try again.")
                continue
        except Exception:
            print("Invalid format! Use x,y,z (e.g., 5,0,0)")
            continue
            
        state = apply_move(state, move_pos)

    print("\n===============================")
    if state['terminal'] == 'draw':
        print("GAME OVER - IT'S A DRAW!")
    else:
        print(f"GAME OVER - PLAYER {state['terminal'].upper()} WINS!")
    print("===============================")

if __name__ == "__main__":
    run_death_match()
