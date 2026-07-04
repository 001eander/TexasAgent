"""Tests for hand evaluation (Seam 2 — deterministic poker logic)."""

from app.engine.hand import evaluate_best_hand, compare_hands
from app.engine.types import Card


def card(s: str) -> Card:
    return Card.from_str(s)


def cards(s: str) -> list[Card]:
    """Parse space-separated card strings."""
    return [Card.from_str(c) for c in s.split()]


class TestHandEvaluation:
    def test_high_card(self):
        hand = cards("Ah Kd 9c 5s 2h")
        result = evaluate_best_hand(hand)
        assert result.name == "High Card"
        assert result.category == 0

    def test_one_pair(self):
        hand = cards("Ah Ad 9c 5s 2h")
        result = evaluate_best_hand(hand)
        assert result.name == "One Pair"
        assert result.category == 1

    def test_two_pair(self):
        hand = cards("Ah Ad Kc Ks 2h")
        result = evaluate_best_hand(hand)
        assert result.name == "Two Pair"
        assert result.category == 2

    def test_three_of_a_kind(self):
        hand = cards("Ah Ad Ac 5s 2h")
        result = evaluate_best_hand(hand)
        assert result.name == "Three of a Kind"
        assert result.category == 3

    def test_straight(self):
        hand = cards("Th Jd Qc Ks Ah")  # Broadway
        result = evaluate_best_hand(hand)
        assert result.name == "Straight"
        assert result.category == 4
        assert result.ranks == [14]  # Ace-high straight

    def test_wheel_straight(self):
        """A-2-3-4-5 is a 5-high straight."""
        hand = cards("Ah 2d 3c 4s 5h")
        result = evaluate_best_hand(hand)
        assert result.name == "Straight"
        assert result.category == 4
        assert result.ranks == [5]

    def test_flush(self):
        hand = cards("Ah Kh 9h 5h 2h")
        result = evaluate_best_hand(hand)
        assert result.name == "Flush"
        assert result.category == 5

    def test_full_house(self):
        hand = cards("Ah Ad Ac Kh Kd")
        result = evaluate_best_hand(hand)
        assert result.name == "Full House"
        assert result.category == 6
        assert result.ranks == [14, 13]  # Aces full of Kings

    def test_four_of_a_kind(self):
        hand = cards("Ah Ad Ac As Kh")
        result = evaluate_best_hand(hand)
        assert result.name == "Four of a Kind"
        assert result.category == 7

    def test_straight_flush(self):
        hand = cards("Th Jh Qh Kh Ah")
        result = evaluate_best_hand(hand)
        assert result.name == "Royal Flush"
        assert result.category == 9

    def test_wheel_straight_flush(self):
        hand = cards("Ah 2h 3h 4h 5h")
        result = evaluate_best_hand(hand)
        assert result.name == "Straight Flush"
        assert result.category == 8
        assert result.ranks == [5]


class TestHandComparison:
    def test_pair_beats_high_card(self):
        pair = cards("Ah Ad 9c 5s 2h")
        high = cards("Kh Qd Jc 9s 8h")
        assert evaluate_best_hand(pair) > evaluate_best_hand(high)

    def test_higher_pair_wins(self):
        aces = cards("Ah Ad 9c 5s 2h")
        kings = cards("Kh Kd Qc Js Th")
        assert evaluate_best_hand(aces) > evaluate_best_hand(kings)

    def test_kicker_matters(self):
        ak = cards("Ah Kd 9c 5s 2h")  # Pair of Aces, K kicker
        aq = cards("Ah Qd 9c 5s 2h")  # Pair of Aces, Q kicker
        assert evaluate_best_hand(ak) > evaluate_best_hand(aq)

    def test_flush_beats_straight(self):
        flush = cards("Ah Kh 9h 5h 2h")
        straight = cards("Th Jd Qc Ks Ah")
        assert evaluate_best_hand(flush) > evaluate_best_hand(straight)

    def test_equal_hands(self):
        hand1 = cards("Ah Kd 9c 5s 2h")
        hand2 = cards("Ah Kd 9c 5s 2h")
        assert evaluate_best_hand(hand1) == evaluate_best_hand(hand2)

    def test_7_card_uses_best_5(self):
        """From 7 cards, the evaluator picks the best 5."""
        # Has a flush if we pick the right 5 hearts
        hand = cards("Ah Kh 9h 5h 2h 2d 2c")
        result = evaluate_best_hand(hand)
        assert result.name == "Flush"


class TestMultiHandComparison:
    def test_single_winner(self):
        # Pair of Aces vs Pair of Kings — Aces win
        # No straight possible with either hand
        winner_7 = cards("Ah Ad 9c 5s 2h 3c 4d")
        loser_7 = cards("Kh Kd 7c 3s 2d 6h 8d")
        result = compare_hands([winner_7, loser_7])
        assert result == [0]

    def test_split_pot(self):
        """Both have the same best 5-card hand."""
        hand1 = cards("Ah Kh Qh Jh Th 2c 3d")  # Royal flush
        hand2 = cards("Ah Kh Qh Jh Th 4c 5d")  # Also royal flush (community cards)
        result = compare_hands([hand1, hand2])
        assert result == [0, 1]
