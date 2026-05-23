"""Base class every CubiCup bot must subclass."""

from abc import ABC, abstractmethod


class BaseBot(ABC):
    """
    Subclass this and implement choose_move().

    choose_move receives the same state dict the Socket.IO server sends:
      {
        'board':          { "x,y,z": "yellow"|"blue"|None, ... },
        'current_player': "yellow"|"blue",
        'your_turn':      True,            # always True when called
        'mandatory':      ["x,y,z", ...],  # non-empty → must pick one of these
        'cubes_left':     { yellow: int, blue: int },
        'legal_moves':    ["x,y,z", ...],
        'move_number':    int,
        'terminal':       None,
      }

    Return one of the strings in state['legal_moves'].
    """

    @property
    def name(self):
        return self.__class__.__name__

    @abstractmethod
    def choose_move(self, state: dict):
        """
        Return one of the strings in state['legal_moves'].
        Alternatively, return a tuple or list: (move_str, debug_info)
        where debug_info is any JSON-serializable object (string, dict, list).
        """
        ...
