#!/usr/bin/env python3
"""Self-contained hand strength evaluator.

Called by pi poker-tools extension.
Usage:
  python3 hand_strength.py --hole Ah Kh --community Qd Jd 9c Th 2s
Output: {"made_hand": "Straight", "category": 4, "ranks": [14]}
"""

import argparse
import itertools
import json
from collections import Counter

RANKS = "23456789TJQKA"
RANK_ORDER = {r: i for i, r in enumerate(RANKS, start=2)}

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


def parse_card(s: str) -> tuple[str, str]:
    return (s[0].upper(), s[1].lower())


def _eval_5(ranks: list[int], suits: list[str]) -> tuple[int, list[int]]:
    rc = Counter(ranks)
    counts = sorted(rc.items(), key=lambda x: (x[1], x[0]), reverse=True)
    flush = len(set(suits)) == 1
    unique = sorted(set(ranks), reverse=True)

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
    best = None
    for combo in itertools.combinations(cards, 5):
        ranks = [RANK_ORDER[c[0]] for c in combo]
        suits = [c[1] for c in combo]
        hr = _eval_5(ranks, suits)
        if best is None or hr > best:
            best = hr
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hole", nargs="+", required=True)
    parser.add_argument("--community", nargs="*", default=[])
    args = parser.parse_args()

    cards = [parse_card(c) for c in args.hole + args.community]

    if len(cards) < 5:
        print(
            json.dumps(
                {
                    "made_hand": "incomplete",
                    "description": f"Need {5 - len(cards)} more cards",
                }
            )
        )
        return

    cat, ranks = best_hand(cards)
    print(
        json.dumps(
            {
                "made_hand": HAND_NAMES[cat],
                "category": cat,
                "ranks": ranks,
            }
        )
    )


if __name__ == "__main__":
    main()
