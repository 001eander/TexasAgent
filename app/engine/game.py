"""Core No-Limit Texas Hold'em game engine — deterministic state machine."""

from .deck import Deck
from .hand import compare_hands
from .types import (
    Action,
    ActionType,
    GameState,
    PlayerState,
    Street,
)


def create_game(
    num_players: int,
    human_indices: list[int] | None = None,
    agent_indices: list[int] | None = None,
    starting_stack: int = 1000,
    small_blind: int = 1,
    big_blind: int = 2,
    seed: int | None = None,
) -> GameState:
    """Create a new game with the given configuration."""
    human_indices = human_indices or []
    agent_indices = agent_indices or []

    players = []
    for i in range(num_players):
        players.append(
            PlayerState(
                name=f"Player{i + 1}",
                stack=starting_stack,
                is_human=i in human_indices,
                is_agent=i in agent_indices,
            )
        )

    state = GameState(
        players=players,
        dealer_index=0,
        small_blind=small_blind,
        big_blind=big_blind,
    )
    return state


def start_hand(state: GameState, seed: int | None = None) -> GameState:
    """Deal a new hand and post blinds."""
    deck = Deck(seed=seed)
    deck.shuffle()

    # Reset per-hand state
    for p in state.players:
        p.hole_cards = []
        p.folded = False
        p.is_all_in = False
        p.current_bet = 0

    state.community_cards = []
    state.pot = 0
    state.side_pots = []
    state.current_bet = 0
    state.street = Street.PREFLOP
    state.min_raise = state.big_blind
    state.last_aggressor_index = -1
    state.actions_this_street = 0
    state.acted_this_street = set()
    state.hand_number += 1

    # Deal hole cards
    for p in state.players:
        if p.stack > 0:
            p.hole_cards = deck.deal(2)

    # Post blinds
    n = len(state.players)
    sb_idx = (state.dealer_index + 1) % n
    bb_idx = (state.dealer_index + 2) % n
    _post_blind(state, sb_idx, state.small_blind)
    _post_blind(state, bb_idx, state.big_blind)
    state.current_bet = state.big_blind

    # First to act: UTG (after big blind)
    state.acting_player_index = (state.dealer_index + 3) % n
    # Skip UTG if they are not active (e.g., all-in from blind posting)
    if not state.players[state.acting_player_index].is_active:
        _advance_to_next_active(state)

    return state


def apply_action(state: GameState, action: Action) -> GameState:
    """Apply a player action and advance the game state."""
    player = state.players[action.player_index]

    match action.action_type:
        case ActionType.FOLD:
            player.folded = True
        case ActionType.CHECK:
            pass  # nothing changes
        case ActionType.CALL:
            _apply_bet(state, action.player_index, action.amount)
        case ActionType.BET | ActionType.RAISE:
            _apply_bet(state, action.player_index, action.amount)
            state.current_bet = player.current_bet
            state.last_aggressor_index = action.player_index
            # After a bet/raise, other active players must act again
            state.acted_this_street = {action.player_index}
        case ActionType.ALL_IN:
            _apply_bet(state, action.player_index, action.amount)
            player.is_all_in = True
            if player.current_bet > state.current_bet:
                state.current_bet = player.current_bet
                state.last_aggressor_index = action.player_index

    # Track action count and who acted this street
    state.actions_this_street += 1
    state.acted_this_street.add(action.player_index)

    # Check if street is over
    if _is_street_complete(state):
        _advance_street(state)
    else:
        _advance_to_next_active(state)

    return state


def legal_actions(state: GameState) -> list[Action]:
    """Return all legal actions for the current acting player."""
    pi = state.acting_player_index
    player = state.players[pi]
    actions: list[Action] = []

    to_call = state.current_bet - player.current_bet

    if to_call == 0:
        # No bet to face — can check or bet
        actions.append(Action(pi, ActionType.CHECK))

        # Bet: min is big blind (or min_raise on later streets)
        min_bet = state.big_blind if state.street == Street.PREFLOP else state.big_blind
        min_bet = max(min_bet, state.min_raise)
        if player.stack >= min_bet:
            actions.append(Action(pi, ActionType.BET, amount=min_bet))
    else:
        # Facing a bet — can fold, call, or raise
        actions.append(Action(pi, ActionType.FOLD))

        if player.stack >= to_call:
            if player.stack == to_call:
                actions.append(Action(pi, ActionType.ALL_IN, amount=to_call))
            else:
                actions.append(Action(pi, ActionType.CALL, amount=to_call))

        # Raise: at least 2x the current bet (or all-in if less)
        min_raise_to = state.current_bet + max(to_call, state.min_raise)
        raise_amount = min_raise_to - player.current_bet
        if player.stack > to_call and player.stack >= raise_amount:
            if player.stack == raise_amount:
                actions.append(Action(pi, ActionType.ALL_IN, amount=raise_amount))
            else:
                actions.append(Action(pi, ActionType.RAISE, amount=raise_amount))

    # All-in is always an option if not already all-in
    if player.stack > 0 and not player.is_all_in:
        all_in_amount = player.stack
        # Avoid duplicates
        if not any(
            a.action_type == ActionType.ALL_IN and a.amount == all_in_amount
            for a in actions
        ):
            actions.append(Action(pi, ActionType.ALL_IN, amount=all_in_amount))

    return actions


def is_hand_over(state: GameState) -> bool:
    """Check if the current hand is complete."""
    active = state.players_in_hand()
    if len(active) == 1:
        return True  # everyone else folded
    if state.street == Street.SHOWDOWN:
        return True
    return False


def showdown(state: GameState) -> list[list[int]]:
    """
    Determine winners at showdown.
    Returns list of winner groups (each group is a list of player indices sharing a pot).
    """
    in_hand = [i for i, p in enumerate(state.players) if p.is_in_hand]

    if len(in_hand) == 1:
        return [[in_hand[0]]]

    # Evaluate each player's best hand
    hands = []
    for i in in_hand:
        cards = state.players[i].hole_cards + state.community_cards
        hands.append(cards)

    winners = compare_hands(hands)
    return [[in_hand[w] for w in winners]]


# ── Private helpers ──────────────────────────────────────────────


def _post_blind(state: GameState, player_idx: int, amount: int) -> None:
    player = state.players[player_idx]
    if player.stack <= amount:
        amount = player.stack
        player.is_all_in = True
    player.stack -= amount
    player.current_bet += amount
    state.pot += amount


def _apply_bet(state: GameState, player_idx: int, amount: int) -> None:
    """Apply a bet/call/raise — deduct from stack, add to pot."""
    player = state.players[player_idx]
    actual = min(amount, player.stack)
    player.stack -= actual
    player.current_bet += actual
    state.pot += actual
    if player.stack == 0:
        player.is_all_in = True


def _is_street_complete(state: GameState) -> bool:
    """Check if the current betting round is complete.

    A round is complete when every active player has acted at least once
    AND all active players have matched the current bet.
    """
    active = state.active_players()

    if len(active) == 0:
        return True  # everyone all-in or folded

    # Every active player must have acted this round
    for i in active:
        if i not in state.acted_this_street:
            return False

    # Everyone must have matched the current bet
    for i in active:
        if state.players[i].current_bet != state.current_bet:
            return False

    return True


def _advance_to_next_active(state: GameState) -> None:
    """Move acting_player_index to the next active player."""
    n = len(state.players)
    for _ in range(n):
        state.acting_player_index = (state.acting_player_index + 1) % n
        if state.players[state.acting_player_index].is_active:
            return


def _advance_street(state: GameState) -> None:
    """Complete the current betting round and deal next street."""
    # Reset per-round state (bets already in pot from _apply_bet)
    for p in state.players:
        p.current_bet = 0

    state.current_bet = 0
    state.last_aggressor_index = -1
    state.actions_this_street = 0
    state.acted_this_street = set()

    deck = Deck()

    match state.street:
        case Street.PREFLOP:
            state.street = Street.FLOP
            deck.shuffle()
            state.community_cards.extend(deck.deal(3))
        case Street.FLOP:
            state.street = Street.TURN
            state.community_cards.extend(deck.deal(1))
        case Street.TURN:
            state.street = Street.RIVER
            state.community_cards.extend(deck.deal(1))
        case Street.RIVER:
            state.street = Street.SHOWDOWN
            return

    # First to act after the flop: first active player after dealer
    n = len(state.players)
    state.acting_player_index = (state.dealer_index + 1) % n
    # Skip if this player isn't active (e.g., folded preflop)
    if not state.players[state.acting_player_index].is_active:
        _advance_to_next_active(state)

    state.min_raise = state.big_blind
