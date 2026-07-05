#!/usr/bin/env python3
"""Self-contained equity calculator — Monte Carlo simulation for Texas Hold'em.

Called by pi poker-tools extension. No external dependencies beyond stdlib.

Usage:
  python3 equity.py --hole Ah Kh --community Qd Jd 9c --opponents 1 --sims 5000
Output: {"win": 0.536, "tie": 0.013, "lose": 0.451, "equity": 0.5425}
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
from collections import Counter

# ── Card primitives ──────────────────────────────────────────

RANKS = "23456789TJQKA"
SUITS = "cdhs"
RANK_ORDER = {r: i for i, r in enumerate(RANKS, start=2)}


def all_cards():
    return [(r, s) for r in RANKS for s in SUITS]


def parse_card(s: str) -> tuple[str, str]:
    return (s[0].upper(), s[1].lower())


# ── Hand evaluation ──────────────────────────────────────────

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


def _eval_5(ranks: list[int], suits: list[str]) -> tuple[int, list[int]]:
    """Evaluate a 5-card hand. Returns (category, tiebreaker_ranks)."""
    rc = Counter(ranks)
    counts = sorted(rc.items(), key=lambda x: (x[1], x[0]), reverse=True)
    grouped = []
    for r, c in counts:
        grouped.extend([r] * c)

    flush = len(set(suits)) == 1
    unique = sorted(set(ranks), reverse=True)

    # Check straight
    straight = False
    straight_high = 0
    if set([14, 2, 3, 4, 5]).issubset(set(unique)):
        straight, straight_high = True, 5
    else:
        for i in range(len(unique) - 4):
            if unique[i] - unique[i + 4] == 4:
                straight, straight_high = True, unique[i]
                break

    if flush and straight:
        return (9 if straight_high == 14 else 8, [straight_high])
    if counts[0][1] == 4:
        return (7, [counts[0][0], counts[1][0]])
    if counts[0][1] == 3 and counts[1][1] == 2:
        return (6, [counts[0][0], counts[1][0]])
    if flush:
        return (5, sorted(ranks, reverse=True))
    if straight:
        return (4, [straight_high])
    if counts[0][1] == 3:
        kickers = [r for r in ranks if r != counts[0][0]][:2]
        return (3, [counts[0][0]] + kickers)
    if counts[0][1] == 2 and counts[1][1] == 2:
        high = max(counts[0][0], counts[1][0])
        low = min(counts[0][0], counts[1][0])
        return (2, [high, low, counts[2][0]])
    if counts[0][1] == 2:
        kickers = [r for r in ranks if r != counts[0][0]][:3]
        return (1, [counts[0][0]] + kickers)
    return (0, sorted(ranks, reverse=True)[:5])


def best_hand(cards: list[tuple[str, str]]) -> tuple[int, list[int]]:
    """Best 5-card hand from up to 7 cards."""
    best = None
    for combo in itertools.combinations(cards, 5):
        ranks = [RANK_ORDER[c[0]] for c in combo]
        suits = [c[1] for c in combo]
        hr = _eval_5(ranks, suits)
        if best is None or hr > best:
            best = hr
    return best


def compare(hands: list[list[tuple[str, str]]]) -> list[int]:
    """Return indices of winning hands."""
    evals = [best_hand(h) for h in hands]
    best = max(evals)
    return [i for i, e in enumerate(evals) if e == best]


# ── Monte Carlo ──────────────────────────────────────────────


def monte_carlo(
    hole: list[str],
    community: list[str],
    opponents: int,
    sims: int,
    seed: int | None,
) -> dict:
    hole_cards = [parse_card(c) for c in hole]
    comm_cards = [parse_card(c) for c in community]
    used = set(hole_cards) | set(comm_cards)
    deck = [c for c in all_cards() if c not in used]

    rng = random.Random(seed)
    wins = ties = 0
    remaining = 5 - len(comm_cards)

    for _ in range(sims):
        rng.shuffle(deck)
        sim_comm = comm_cards + deck[:remaining]
        idx = remaining

        opp_hands = []
        for _ in range(opponents):
            opp_hands.append(deck[idx : idx + 2])
            idx += 2

        all_hands = [hole_cards + sim_comm] + [oh + sim_comm for oh in opp_hands]
        winners = compare(all_hands)

        if 0 in winners and len(winners) == 1:
            wins += 1
        elif 0 in winners:
            ties += 1

    return {
        "win": wins / sims,
        "tie": ties / sims,
        "lose": (sims - wins - ties) / sims,
        "equity": (wins + ties / 2) / sims,
    }


# ── CLI ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo poker equity")
    parser.add_argument("--hole", nargs="+", required=True)
    parser.add_argument("--community", nargs="*", default=[])
    parser.add_argument("--opponents", type=int, default=1)
    parser.add_argument("--sims", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    result = monte_carlo(
        hole=args.hole,
        community=args.community,
        opponents=args.opponents,
        sims=min(args.sims, 20000),
        seed=args.seed,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
