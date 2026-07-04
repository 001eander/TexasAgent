"""Tests for poker engine types and cards."""

import pytest
from app.engine.types import ALL_RANKS, ALL_SUITS, RANK_ORDER, Card, Rank, Suit


class TestCard:
    def test_create_card(self):
        c = Card(Rank.ACE, Suit.SPADES)
        assert c.rank == Rank.ACE
        assert c.suit == Suit.SPADES
        assert str(c) == "As"

    def test_from_str(self):
        c = Card.from_str("Ah")
        assert c.rank == Rank.ACE
        assert c.suit == Suit.HEARTS

    def test_from_str_lowercase(self):
        c = Card.from_str("td")
        assert c.rank == Rank.TEN
        assert c.suit == Suit.DIAMONDS

    def test_from_str_invalid(self):
        with pytest.raises(ValueError):
            Card.from_str("A")
        with pytest.raises(ValueError):
            Card.from_str("invalid")

    def test_card_ordering(self):
        low = Card(Rank.TWO, Suit.CLUBS)
        high = Card(Rank.ACE, Suit.CLUBS)
        assert low < high
        assert low <= high
        assert high > low

    def test_cards_unique(self):
        c1 = Card(Rank.KING, Suit.HEARTS)
        c2 = Card(Rank.KING, Suit.HEARTS)
        c3 = Card(Rank.KING, Suit.SPADES)
        assert c1 == c2
        assert c1 != c3
        assert hash(c1) == hash(c2)

    def test_rank_values(self):
        assert RANK_ORDER[Rank.TWO] == 2
        assert RANK_ORDER[Rank.ACE] == 14
        assert RANK_ORDER[Rank.KING] > RANK_ORDER[Rank.QUEEN]

    def test_full_deck_size(self):
        assert len(ALL_RANKS) == 13
        assert len(ALL_SUITS) == 4
        assert len(ALL_RANKS) * len(ALL_SUITS) == 52


class TestGameState:
    def test_position_names_6max(self):
        from app.engine.types import GameState, PlayerState

        players = [PlayerState(name=f"P{i}", stack=1000) for i in range(6)]
        state = GameState(players=players, dealer_index=0)

        assert state._position_name(0) == "BTN"
        assert state._position_name(1) == "SB"
        assert state._position_name(2) == "BB"
        assert state._position_name(3) == "UTG"
        assert state._position_name(4) == "HJ"
        assert state._position_name(5) == "CO"

    def test_active_players(self):
        from app.engine.types import GameState, PlayerState

        players = [PlayerState(name=f"P{i}", stack=1000) for i in range(3)]
        players[1].folded = True
        players[2].is_all_in = True
        state = GameState(players=players)
        assert state.active_players() == [0]
        assert state.players_in_hand() == [0, 2]

    def test_player_view_hides_hole_cards(self):
        from app.engine.types import Card, GameState, PlayerState, Rank, Suit

        players = [
            PlayerState(
                name="Hero",
                stack=1000,
                hole_cards=[Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)],
                is_human=True,
            ),
            PlayerState(
                name="Villain",
                stack=1000,
                hole_cards=[
                    Card(Rank.QUEEN, Suit.HEARTS),
                    Card(Rank.JACK, Suit.HEARTS),
                ],
                is_agent=True,
            ),
        ]
        state = GameState(
            players=players, community_cards=[Card(Rank.TEN, Suit.DIAMONDS)]
        )
        view = state.player_view(0)
        assert view["hole_cards"] == ["As", "Ks"]
        assert view["community_cards"] == ["Td"]
        assert len(view["opponents"]) == 1
        assert view["opponents"][0]["name"] == "Villain"
        # Opponent hole cards are NOT exposed
        assert "hole_cards" not in view["opponents"][0]
