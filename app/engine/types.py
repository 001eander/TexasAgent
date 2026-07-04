"""Core domain types for Texas Hold'em poker engine."""

from dataclasses import dataclass, field
from enum import Enum


class Suit(str, Enum):
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"
    SPADES = "s"


class Rank(str, Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "T"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


RANK_ORDER: dict[Rank, int] = {
    Rank.TWO: 2,
    Rank.THREE: 3,
    Rank.FOUR: 4,
    Rank.FIVE: 5,
    Rank.SIX: 6,
    Rank.SEVEN: 7,
    Rank.EIGHT: 8,
    Rank.NINE: 9,
    Rank.TEN: 10,
    Rank.JACK: 11,
    Rank.QUEEN: 12,
    Rank.KING: 13,
    Rank.ACE: 14,
}

ALL_RANKS = list(Rank)
ALL_SUITS = list(Suit)


@dataclass(frozen=True, order=True)
class Card:
    rank: Rank = field(compare=True)
    suit: Suit = field(compare=True)

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"

    @classmethod
    def from_str(cls, s: str) -> "Card":
        if len(s) != 2:
            raise ValueError(f"Invalid card string: {s}")
        return cls(rank=Rank(s[0].upper()), suit=Suit(s[1].lower()))


class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass(frozen=True)
class Action:
    player_index: int
    action_type: ActionType
    amount: int = 0

    def __str__(self) -> str:
        match self.action_type:
            case ActionType.FOLD:
                return "folds"
            case ActionType.CHECK:
                return "checks"
            case ActionType.CALL:
                return f"calls {self.amount}"
            case ActionType.BET:
                return f"bets {self.amount}"
            case ActionType.RAISE:
                return f"raises to {self.amount}"
            case ActionType.ALL_IN:
                return f"all-in {self.amount}"


@dataclass
class PlayerState:
    name: str
    stack: int
    hole_cards: list[Card] = field(default_factory=list)
    folded: bool = False
    is_all_in: bool = False
    current_bet: int = 0  # amount this player has put in this betting round
    is_human: bool = False
    is_agent: bool = False

    @property
    def is_active(self) -> bool:
        return not self.folded and not self.is_all_in

    @property
    def is_in_hand(self) -> bool:
        return not self.folded


@dataclass
class SidePot:
    amount: int
    eligible_players: set[int]  # player indices


@dataclass
class GameState:
    players: list[PlayerState]
    community_cards: list[Card] = field(default_factory=list)
    pot: int = 0
    side_pots: list[SidePot] = field(default_factory=list)
    current_bet: int = 0  # the current bet to match
    dealer_index: int = 0
    acting_player_index: int = 0
    street: Street = Street.PREFLOP
    min_raise: int = 0
    last_aggressor_index: int = -1
    hand_number: int = 0
    small_blind: int = 1
    big_blind: int = 2
    actions_this_street: int = 0  # number of actions taken in current betting round
    acted_this_street: set[int] = field(
        default_factory=set
    )  # players who have acted this round

    @property
    def big_blind_amount(self) -> int:
        return self.big_blind

    def active_players(self) -> list[int]:
        """Return indices of players still active (not folded, not all-in)."""
        return [i for i, p in enumerate(self.players) if p.is_active]

    def players_in_hand(self) -> list[int]:
        """Return indices of players still in the hand (not folded)."""
        return [i for i, p in enumerate(self.players) if p.is_in_hand]

    def player_view(self, player_index: int) -> dict:
        """Return the game state as visible to a specific player (hidden cards hidden)."""
        p = self.players[player_index]
        return {
            "hand_number": self.hand_number,
            "hole_cards": [str(c) for c in p.hole_cards],
            "community_cards": [str(c) for c in self.community_cards],
            "pot": self.pot,
            "current_bet": self.current_bet,
            "my_stack": p.stack,
            "my_bet": p.current_bet,
            "street": self.street.value,
            "dealer_index": self.dealer_index,
            "acting_player_index": self.acting_player_index,
            "position": self._position_name(player_index),
            "opponents": [
                {
                    "name": opp.name,
                    "stack": opp.stack,
                    "folded": opp.folded,
                    "is_all_in": opp.is_all_in,
                    "current_bet": opp.current_bet,
                }
                for i, opp in enumerate(self.players)
                if i != player_index
            ],
        }

    def _position_name(self, player_index: int) -> str:
        n = len(self.players)
        offset = (player_index - self.dealer_index) % n
        if offset == 0:
            return "BTN"
        if offset == 1:
            return "SB"
        if offset == 2:
            return "BB"
        if offset == n - 1:
            return "CO"
        if offset == n - 2:
            return "HJ"
        if offset == 3:
            return "UTG"
        return f"UTG+{offset - 3}"
