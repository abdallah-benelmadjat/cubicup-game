import random
from .base import BaseBot


class RandomBot(BaseBot):
    """Picks a uniformly random legal move."""

    def choose_move(self, state):
        return random.choice(state['legal_moves'])
