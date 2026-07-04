"""Deck management with deterministic seeding for testing."""

import random

from .types import ALL_RANKS, ALL_SUITS, Card


class Deck:
    """A standard 52-card deck with shuffle."""

    def __init__(self, seed: int | None = None):
        self.cards: list[Card] = [
            Card(rank=r, suit=s) for r in ALL_RANKS for s in ALL_SUITS
        ]
        self._rng = random.Random(seed)

    def shuffle(self) -> None:
        self._rng.shuffle(self.cards)

    def deal(self, n: int = 1) -> list[Card]:
        if n > len(self.cards):
            raise ValueError(
                f"Not enough cards: {len(self.cards)} remaining, {n} requested"
            )
        dealt = self.cards[:n]
        self.cards = self.cards[n:]
        return dealt

    def __len__(self) -> int:
        return len(self.cards)

    def reset(self) -> None:
        self.cards = [Card(rank=r, suit=s) for r in ALL_RANKS for s in ALL_SUITS]
