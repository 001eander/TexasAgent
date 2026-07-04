#!/usr/bin/env python3
"""CLI hand strength evaluator — called by pi poker tools extension."""

import argparse
import json
import sys

sys.path.insert(0, "/".join(__file__.split("/")[:-3]))

from app.tools.equity import evaluate_hand_strength


def main():
    parser = argparse.ArgumentParser(description="Hand strength evaluator")
    parser.add_argument("--hole", nargs="+", required=True, help="Hole cards")
    parser.add_argument("--community", nargs="*", default=[], help="Community cards")
    args = parser.parse_args()

    result = evaluate_hand_strength(
        hole_cards=args.hole,
        community_cards=args.community,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
