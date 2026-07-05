"""FastAPI application — TexasAgent web server.

Serves the poker table UI and manages game sessions via WebSocket.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.agent.pi_client import PiRpcClient, PiRpcConfig
from app.engine.game import (
    apply_action,
    create_game,
    is_hand_over,
    legal_actions,
    showdown,
    start_hand,
)
from app.engine.types import Action, ActionType, GameState, Street

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── In-memory store (replace with SQLite later) ────────────
tables: dict[str, GameState] = {}
connections: dict[str, list[WebSocket]] = {}

# ── pi RPC client ──────────────────────────────────────────
_pi_client: PiRpcClient | None = None


def _get_pi_extension_path() -> str:
    import os

    return os.path.join(
        os.path.dirname(__file__), "..", "pi-package", "extensions", "poker-tools.ts"
    )


templates = Jinja2Templates(directory="app/templates")


def game_view(state: GameState, player_index: int | None = None) -> dict:
    """Serialize game state for JSON/websocket."""
    if player_index is not None:
        view = state.player_view(player_index)
    else:
        view = {}

    return {
        "hand_number": state.hand_number,
        "street": state.street.value,
        "pot": state.pot,
        "current_bet": state.current_bet,
        "community_cards": [str(c) for c in state.community_cards],
        "players": [
            {
                "name": p.name,
                "stack": p.stack,
                "folded": p.folded,
                "is_all_in": p.is_all_in,
                "current_bet": p.current_bet,
                "is_human": p.is_human,
                "is_agent": p.is_agent,
                "hole_cards": (
                    [str(c) for c in p.hole_cards]
                    if (player_index is not None and i == player_index)
                    or p.folded
                    or state.street == Street.SHOWDOWN
                    else ["??", "??"]
                ),
                "position": state._position_name(i),
            }
            for i, p in enumerate(state.players)
        ],
        "acting_player_index": state.acting_player_index,
        "dealer_index": state.dealer_index,
        "player_view": view if player_index is not None else None,
    }


async def broadcast(table_id: str, player_index: int | None = None) -> None:
    """Push current game state to all connected clients."""
    if table_id not in tables:
        return
    state = tables[table_id]
    data = game_view(state, player_index)

    if table_id in connections:
        for ws in connections[table_id]:
            try:
                await ws.send_json({"type": "game_state", "data": data})
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pi_client
    logger.info("TexasAgent starting...")

    # Try to start pi RPC
    config = PiRpcConfig(
        extension_path=_get_pi_extension_path(),
    )
    _pi_client = PiRpcClient(config)
    try:
        await _pi_client.start()
        logger.info("pi RPC connected — AI agents will use LLM")
    except Exception as e:
        logger.warning(
            f"pi RPC unavailable ({e}) — AI agents will use heuristic fallback"
        )
        _pi_client = None

    yield

    if _pi_client:
        await _pi_client.stop()
    logger.info("TexasAgent shutting down...")


app = FastAPI(title="TexasAgent", lifespan=lifespan)


# ── Pages ───────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})  # type: ignore[arg-type]


@app.get("/table/{table_id}", response_class=HTMLResponse)
async def table_page(request: Request, table_id: str):
    return templates.TemplateResponse(
        request,
        "table.html",
        {  # type: ignore[arg-type]
            "request": request,
            "table_id": table_id,
        },
    )


# ── REST API ────────────────────────────────────────────────


@app.post("/api/table/create")
async def create_table(
    num_players: int = 6,
    human_indices: str = "0",
    agent_indices: str = "1,2,3,4,5",
    starting_stack: int = 1000,
):
    human = [int(i) for i in human_indices.split(",") if i.strip()]
    agent = [int(i) for i in agent_indices.split(",") if i.strip()]

    import uuid

    table_id = str(uuid.uuid4())[:8]
    state = create_game(
        num_players=num_players,
        human_indices=human,
        agent_indices=agent,
        starting_stack=starting_stack,
    )
    state = start_hand(state, seed=42)
    tables[table_id] = state
    return {"table_id": table_id, "state": game_view(state, 0)}


@app.get("/api/table/{table_id}")
async def get_table(table_id: str):
    if table_id not in tables:
        return {"error": "Table not found"}
    state = tables[table_id]
    return game_view(state, 0)


@app.post("/api/table/{table_id}/action")
async def player_action(table_id: str, action_type: str, amount: int = 0):
    if table_id not in tables:
        return {"error": "Table not found"}

    state = tables[table_id]
    pi = state.acting_player_index
    player = state.players[pi]

    if not player.is_human:
        return {"error": "Not a human player's turn"}

    # Build action
    try:
        at = ActionType(action_type)
    except ValueError:
        return {"error": f"Invalid action: {action_type}"}

    # Validate
    legal = legal_actions(state)
    legal_types = {(a.action_type, a.amount) for a in legal}

    action = Action(pi, at, amount)
    if (at, amount) not in legal_types:
        return {
            "error": f"Illegal action: {at.value} {amount}",
            "legal": [{"type": a.action_type.value, "amount": a.amount} for a in legal],
        }

    state = apply_action(state, action)
    tables[table_id] = state
    await broadcast(table_id, pi)

    # Auto-run agent actions
    await _run_agent_actions(table_id)

    return game_view(state, pi)


def _format_prompt(state: GameState, player_index: int) -> str:
    """Format game state as a natural language prompt for the LLM."""
    p = state.players[player_index]
    to_call = state.current_bet - p.current_bet

    lines = [
        "You are playing No-Limit Texas Hold'em. Make a decision.",
        "",
        f"**Your hand:** {', '.join(str(c) for c in p.hole_cards)}",
        f"**Board:** {', '.join(str(c) for c in state.community_cards) if state.community_cards else '(preflop)'}",
        f"**Street:** {state.street.value}",
        f"**Pot:** {state.pot} | **Your stack:** {p.stack} | **To call:** {to_call}",
        f"**Position:** {state._position_name(player_index)}",
        "",
        "**Opponents:**",
    ]

    for i, opp in enumerate(state.players):
        if i == player_index:
            continue
        lines.append(
            f"  - {opp.name} ({state._position_name(i)}): "
            f"Stack {opp.stack}{' (FOLDED)' if opp.folded else ''}"
            f"{' (ALL-IN)' if opp.is_all_in else ''}"
        )

    lines.append("")
    lines.append("**Legal actions:**")
    for a in legal_actions(state):
        if a.player_index == player_index:
            lines.append(f"  - {a.action_type.value} {a.amount if a.amount else ''}")

    lines.append("")
    lines.append(
        "Use available tools (poker_equity, poker_pot_odds, poker_hand_strength, "
        "poker_opponent_stats) to analyze the situation, then output your decision: "
        "FOLD / CALL / RAISE <amount>"
    )

    return "\n".join(lines)


async def _run_agent_actions(table_id: str) -> None:
    """Auto-play agent turns until a human player needs to act."""
    state = tables[table_id]
    max_iterations = 20  # safety cap

    for _ in range(max_iterations):
        if is_hand_over(state):
            winners = showdown(state)
            logger.info(f"Hand {state.hand_number} over. Winners: {winners}")
            # Award pot to winners
            if winners:
                win_amount = state.pot // len(winners[0])
                for wi in winners[0]:
                    state.players[wi].stack += win_amount
            await broadcast(table_id)
            # Start next hand
            state = start_hand(state, seed=state.hand_number)
            tables[table_id] = state
            await broadcast(table_id)
            continue

        pi = state.acting_player_index
        player = state.players[pi]

        if player.is_human:
            await broadcast(table_id, pi)
            break  # wait for human input

        if player.folded or player.is_all_in:
            # Auto-advance
            state = apply_action(state, Action(pi, ActionType.CHECK))
            tables[table_id] = state
            await broadcast(table_id)
            continue

        # Agent decision — use pi RPC if available, else heuristic fallback
        if _pi_client and _pi_client.is_running:
            prompt = _format_prompt(state, pi)
            logger.info(f"Asking pi for {player.name}'s decision...")
            decision = await _pi_client.decide(prompt)

            if decision.action:
                # Validate and apply
                legal = legal_actions(state)
                legal_set = {(a.action_type, a.amount) for a in legal}
                raw = decision.action

                # Map CALL with 0 amount to CHECK if check is legal
                if raw.action_type == ActionType.CALL and raw.amount == 0:
                    raw = Action(pi, ActionType.CHECK, 0)

                if (raw.action_type, raw.amount) in legal_set:
                    action = Action(pi, raw.action_type, raw.amount)
                    logger.info(
                        f"pi decision: {action.action_type.value} {action.amount} — {decision.reasoning[:100]}"
                    )
                else:
                    logger.warning(
                        f"pi returned illegal action {raw.action_type.value} {raw.amount}, falling back"
                    )
                    action = _heuristic_action(state, pi)
            else:
                logger.warning("pi returned no action, falling back")
                action = _heuristic_action(state, pi)
        else:
            action = _heuristic_action(state, pi)

        state = apply_action(state, action)
        tables[table_id] = state
        await broadcast(table_id)


# ── WebSocket ───────────────────────────────────────────────


def _heuristic_action(state: GameState, pi: int) -> Action:
    """Simple fallback when pi RPC is not available."""
    player = state.players[pi]
    to_call = state.current_bet - player.current_bet
    if to_call == 0:
        return Action(pi, ActionType.CHECK)
    if to_call <= max(player.stack * 0.05, player.stack):
        return Action(pi, ActionType.CALL, amount=min(to_call, player.stack))
    import random

    if random.random() < 0.5:
        return Action(pi, ActionType.CALL, amount=min(to_call, player.stack))
    return Action(pi, ActionType.FOLD)


@app.websocket("/ws/{table_id}")
async def websocket_endpoint(ws: WebSocket, table_id: str):
    await ws.accept()

    if table_id not in connections:
        connections[table_id] = []
    connections[table_id].append(ws)

    # Send current state on connect
    if table_id in tables:
        await ws.send_json(
            {
                "type": "game_state",
                "data": game_view(tables[table_id], 0),
            }
        )

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "action":
                # Delegate to REST endpoint
                result = await player_action(
                    table_id=table_id,
                    action_type=data["action_type"],
                    amount=data.get("amount", 0),
                )
                if "error" in result:
                    await ws.send_json({"type": "error", "message": result["error"]})
    except WebSocketDisconnect:
        pass
    finally:
        if table_id in connections:
            connections[table_id].remove(ws)
