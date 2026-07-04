#!/usr/bin/env python3
"""CLI equity calculator — called by pi poker tools extension."""

import argparse
import json
import sys

# Add parent to path for running within package context
sys.path.insert(0, "/".join(__file__.split("/")[:-3]))

from app.tools.equity import calculate_equity


def main():
    parser = argparse.ArgumentParser(description="Texas Hold'em equity calculator")
    parser.add_argument("--hole", nargs="+", required=True, help="Hole cards")
    parser.add_argument("--community", nargs="*", default=[], help="Community cards")
    parser.add_argument("--opponents", type=int, default=1, help="Number of opponents")
    parser.add_argument("--sims", type=int, default=5000, help="Simulation count")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    args = parser.parse_args()

    result = calculate_equity(
        hole_cards=args.hole,
        community_cards=args.community,
        num_opponents=args.opponents,
        num_simulations=args.sims,
        seed=args.seed,
    )

    print(
        json.dumps(
            {
                "win": result.win,
                "tie": result.tie,
                "lose": result.lose,
                "equity": result.equity,
            }
        )
    )


if __name__ == "__main__":
    main()
