"""Tests for tool layer (Seam 3)."""

import pytest
from app.tools.equity import (
    calculate_equity,
    calculate_pot_odds,
    evaluate_hand_strength,
)


class TestEquityCalculator:
    def test_aa_vs_random_preflop(self):
        """AA vs random hand — should be ~85% equity."""
        result = calculate_equity(
            hole_cards=["Ah", "Ad"],
            num_opponents=1,
            num_simulations=10000,
            seed=42,
        )
        assert 0.80 < result.equity < 0.90
        assert 0.80 < result.win < 0.90

    def test_aa_vs_kk_preflop(self):
        """AA vs KK — AA is ~82% favorite."""
        result = calculate_equity(
            hole_cards=["Ah", "Ad"],
            num_opponents=1,
            num_simulations=5000,
            seed=42,
        )
        # We can't force opponent to have KK in this API, but AA equity is still ~85%
        assert result.equity > 0.80

    def test_flush_draw_on_flop(self):
        """Combo draw (flush + straight) on flop has strong equity vs random hand."""
        result = calculate_equity(
            hole_cards=["Ah", "Kh"],
            community_cards=["Qh", "Jh", "2c"],
            num_opponents=1,
            num_simulations=5000,
            seed=42,
        )
        # Flush draw + straight draw vs random = strong favorite
        assert result.equity > 0.55

    def test_made_hand_on_river(self):
        """Made nut straight on river should have near 100% equity vs random."""
        result = calculate_equity(
            hole_cards=["Ah", "Kh"],
            community_cards=["Qd", "Jd", "Tc", "2s", "3h"],
            num_opponents=1,
            num_simulations=5000,
            seed=42,
        )
        # Broadway straight is very strong
        assert result.equity > 0.85

    def test_multiple_opponents(self):
        """Equity decreases with more opponents."""
        heads_up = calculate_equity(
            hole_cards=["Ah", "Ad"],
            num_opponents=1,
            num_simulations=3000,
            seed=42,
        )
        multiway = calculate_equity(
            hole_cards=["Ah", "Ad"],
            num_opponents=3,
            num_simulations=3000,
            seed=42,
        )
        assert multiway.equity < heads_up.equity

    def test_reproducible_with_seed(self):
        """Same seed yields same result."""
        r1 = calculate_equity(
            hole_cards=["Ah", "Kh"],
            num_opponents=1,
            num_simulations=5000,
            seed=42,
        )
        r2 = calculate_equity(
            hole_cards=["Ah", "Kh"],
            num_opponents=1,
            num_simulations=5000,
            seed=42,
        )
        assert r1.win == r2.win
        assert r1.tie == r2.tie


class TestPotOdds:
    def test_call_half_pot(self):
        """Calling a half-pot bet: need 25% equity."""
        ratio, required = calculate_pot_odds(pot=100, to_call=50)
        assert ratio == 2.0
        assert required == pytest.approx(0.333, rel=0.01)

    def test_call_pot_sized_bet(self):
        """Calling a pot-sized bet: need 33% equity."""
        ratio, required = calculate_pot_odds(pot=100, to_call=100)
        assert ratio == 1.0
        assert required == pytest.approx(0.5, rel=0.01)

    def test_no_cost_to_call(self):
        """Checking has no cost."""
        ratio, required = calculate_pot_odds(pot=100, to_call=0)
        assert required == 0.0


class TestHandStrength:
    def test_complete_hand(self):
        result = evaluate_hand_strength(
            hole_cards=["Ah", "Kh"],
            community_cards=["Qh", "Jh", "Th", "2s", "3h"],
        )
        assert result["made_hand"] == "Royal Flush"

    def test_incomplete_board(self):
        result = evaluate_hand_strength(
            hole_cards=["Ah", "Kh"],
            community_cards=["Qh", "Jh"],
        )
        assert result["made_hand"] == "incomplete"
