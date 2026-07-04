"""Hand evaluation using 7-card best-5 hand ranking."""

from collections import Counter
from functools import total_ordering
from itertools import combinations

from .types import RANK_ORDER, Card


@total_ordering
class HandRank:
    """Comparable hand rank result."""

    HAND_NAMES = [
        "High Card",
        "One Pair",
        "Two Pair",
        "Three of a Kind",
        "Straight",
        "Flush",
        "Full House",
        "Four of a Kind",
        "Straight Flush",
        "Royal Flush",
    ]

    def __init__(self, category: int, ranks: list[int]):
        self.category = category  # 0–9
        self.ranks = ranks  # tiebreaker ranks, high to low

    @property
    def name(self) -> str:
        return self.HAND_NAMES[self.category]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HandRank):
            return NotImplemented
        return self.category == other.category and self.ranks == other.ranks

    def __lt__(self, other: "HandRank") -> bool:
        if self.category != other.category:
            return self.category < other.category
        for a, b in zip(self.ranks, other.ranks):
            if a != b:
                return a < b
        return False

    def __hash__(self) -> int:
        return hash((self.category, tuple(self.ranks)))


def _is_flush(cards: list[Card]) -> bool:
    suits = Counter(c.suit for c in cards)
    return any(count >= 5 for count in suits.values())


def _is_straight(ranks: list[int]) -> tuple[bool, int]:
    """Check if ranks contain a straight. Returns (is_straight, high_card)."""
    unique = sorted(set(ranks), reverse=True)
    # Handle wheel (A-2-3-4-5)
    if set([14, 2, 3, 4, 5]).issubset(set(unique)):
        return True, 5
    for i in range(len(unique) - 4):
        if unique[i] - unique[i + 4] == 4:
            return True, unique[i]
    return False, 0


def evaluate_best_hand(cards: list[Card]) -> HandRank:
    """Evaluate the best 5-card hand from up to 7 cards."""
    if len(cards) < 5:
        raise ValueError(f"Need at least 5 cards, got {len(cards)}")

    best: HandRank | None = None

    for combo in combinations(cards, 5):
        hr = _evaluate_5_cards(list(combo))
        if best is None or hr > best:
            best = hr

    assert best is not None
    return best


def _evaluate_5_cards(cards: list[Card]) -> HandRank:
    """Evaluate a 5-card poker hand."""
    ranks = sorted([RANK_ORDER[c.rank] for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    rank_counts = Counter(ranks)
    count_values = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    # ranks grouped by frequency, high cards first within each group
    grouped = []
    for r, cnt in count_values:
        grouped.extend([r] * cnt)

    is_flush = len(set(suits)) == 1
    is_straight, straight_high = _is_straight(ranks)

    # Royal/Straight flush
    if is_flush and is_straight:
        if straight_high == 14:
            return HandRank(9, [14])
        return HandRank(8, [straight_high])

    # Four of a kind
    if count_values[0][1] == 4:
        quad = count_values[0][0]
        kicker = count_values[1][0]
        return HandRank(7, [quad, kicker])

    # Full house
    if count_values[0][1] == 3 and count_values[1][1] == 2:
        trips = count_values[0][0]
        pair = count_values[1][0]
        return HandRank(6, [trips, pair])

    # Flush
    if is_flush:
        return HandRank(5, ranks)

    # Straight
    if is_straight:
        return HandRank(4, [straight_high])

    # Three of a kind
    if count_values[0][1] == 3:
        trips = count_values[0][0]
        kickers = [r for r in ranks if r != trips][:2]
        return HandRank(3, [trips] + kickers)

    # Two pair
    if count_values[0][1] == 2 and count_values[1][1] == 2:
        high_pair = max(count_values[0][0], count_values[1][0])
        low_pair = min(count_values[0][0], count_values[1][0])
        kicker = count_values[2][0]
        return HandRank(2, [high_pair, low_pair, kicker])

    # One pair
    if count_values[0][1] == 2:
        pair = count_values[0][0]
        kickers = [r for r in ranks if r != pair][:3]
        return HandRank(1, [pair] + kickers)

    # High card
    return HandRank(0, ranks[:5])


def compare_hands(hands: list[list[Card]]) -> list[int]:
    """Compare multiple hands, return indices of winners."""
    evaluations = [evaluate_best_hand(h) for h in hands]
    best = max(evaluations)
    return [i for i, ev in enumerate(evaluations) if ev == best]
