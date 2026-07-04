"""Monte Carlo equity calculator for Texas Hold'em hands."""

import random
from dataclasses import dataclass

from app.engine.hand import compare_hands
from app.engine.types import ALL_RANKS, ALL_SUITS, Card


@dataclass
class EquityResult:
    win: float
    tie: float
    lose: float

    @property
    def equity(self) -> float:
        """Total equity = win% + tie% / N (split among tied players)."""
        return self.win + self.tie / 2


def _all_cards() -> list[Card]:
    return [Card(rank=r, suit=s) for r in ALL_RANKS for s in ALL_SUITS]


def calculate_equity(
    hole_cards: list[str],
    community_cards: list[str] | None = None,
    num_opponents: int = 1,
    num_simulations: int = 5000,
    seed: int | None = None,
) -> EquityResult:
    """
    Monte Carlo equity calculation.

    Args:
        hole_cards: List of card strings, e.g. ["Ah", "Kh"]
        community_cards: Known community cards, e.g. ["Qd", "Jd", "9c"]
        num_opponents: Number of opponents (default 1)
        num_simulations: Number of Monte Carlo trials
        seed: Random seed for reproducibility

    Returns:
        EquityResult with win/tie/lose fractions
    """
    hero = [Card.from_str(c) for c in hole_cards]
    known = [Card.from_str(c) for c in (community_cards or [])]

    # Remaining deck
    used = set(hero) | set(known)
    deck = [c for c in _all_cards() if c not in used]

    rng = random.Random(seed)
    wins = 0
    ties = 0

    remaining_community = 5 - len(known)

    for _ in range(num_simulations):
        # Shuffle remaining deck
        rng.shuffle(deck)

        # Deal community cards
        sim_community = known + deck[:remaining_community]
        cards_used = remaining_community

        # Deal opponent hands
        opponent_hands = []
        for _ in range(num_opponents):
            opp = deck[cards_used : cards_used + 2]
            opponent_hands.append(opp)
            cards_used += 2

        # Evaluate
        hero_hand = hero + sim_community
        all_hands = [hero_hand] + [opp + sim_community for opp in opponent_hands]
        winners = compare_hands(all_hands)

        if 0 in winners and len(winners) == 1:
            wins += 1
        elif 0 in winners:
            ties += 1

    return EquityResult(
        win=wins / num_simulations,
        tie=ties / num_simulations,
        lose=(num_simulations - wins - ties) / num_simulations,
    )


def calculate_pot_odds(pot: int, to_call: int) -> tuple[float, float]:
    """
    Calculate pot odds and required equity.

    Args:
        pot: Current pot size (before your call)
        to_call: Amount needed to call

    Returns:
        (pot_odds_ratio, required_equity_pct)
    """
    if to_call == 0:
        return (0.0, 0.0)
    required = to_call / (pot + to_call)
    return (pot / to_call, required)


def evaluate_hand_strength(hole_cards: list[str], community_cards: list[str]) -> dict:
    """Return a description of current hand strength."""
    from app.engine.hand import evaluate_best_hand

    hero = [Card.from_str(c) for c in hole_cards]
    community = [Card.from_str(c) for c in community_cards]
    all_cards = hero + community

    if len(all_cards) < 5:
        return {
            "made_hand": "incomplete",
            "description": f"Need {5 - len(all_cards)} more cards",
        }

    best = evaluate_best_hand(all_cards)
    return {
        "made_hand": best.name,
        "category": best.category,
        "ranks": best.ranks,
    }
