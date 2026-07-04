"""Pi RPC client — communicates with pi coding agent via stdin/stdout JSON.

Spawns pi in headless RPC mode and sends game state prompts.
Parses structured actions from the LLM's response.
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field

from app.engine.types import Action, ActionType

logger = logging.getLogger(__name__)


@dataclass
class PiRpcConfig:
    pi_path: str = "pi"
    model: str = "deepseek/deepseek-v4-pro"
    extension_path: str | None = None  # path to poker-tools.ts
    thinking_level: str = "medium"
    no_session: bool = True


@dataclass
class AgentDecision:
    action: Action
    reasoning: str = ""


@dataclass
class PiRpcClient:
    config: PiRpcConfig = field(default_factory=PiRpcConfig)
    _proc: subprocess.Popen | None = field(default=None, init=False)
    _pending_ui_requests: dict[str, asyncio.Future] = field(
        default_factory=dict, init=False
    )

    def start(self) -> None:
        """Spawn pi in RPC mode."""
        args = [
            self.config.pi_path,
            "--mode",
            "rpc",
            "--model",
            self.config.model,
        ]
        if self.config.no_session:
            args.append("--no-session")
        if self.config.extension_path:
            args.extend(["-e", self.config.extension_path])

        env = os.environ.copy()

        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        logger.info(f"pi RPC started (pid={self._proc.pid})")

    def stop(self) -> None:
        """Terminate the pi subprocess."""
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
            logger.info("pi RPC stopped")

    async def decide(self, game_prompt: str) -> AgentDecision:
        """Send a game state prompt to pi and parse the decision."""
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            raise RuntimeError("pi RPC not started. Call start() first.")

        # Send prompt
        cmd = json.dumps({"type": "prompt", "message": game_prompt}) + "\n"
        self._proc.stdin.write(cmd)
        self._proc.stdin.flush()

        reasoning_parts: list[str] = []
        tool_results: list[dict] = []
        final_text: list[str] = []

        # Read events
        while True:
            line = self._proc.stdout.readline()
            if not line:
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            match event.get("type"):
                case "message_update":
                    delta = event.get("assistantMessageEvent", {})
                    if delta.get("type") == "text_delta":
                        final_text.append(delta.get("delta", ""))
                    elif delta.get("type") == "thinking_delta":
                        reasoning_parts.append(delta.get("thinking", ""))

                case "tool_execution_end":
                    tool_results.append(
                        {
                            "name": event.get("toolName", "unknown"),
                            "result": event.get("result", {}),
                        }
                    )

                case "agent_end":
                    break

                case "extension_ui_request":
                    # Auto-respond to simple UI requests
                    await self._handle_ui_request(event)

        reasoning = "".join(reasoning_parts)
        text = "".join(final_text)

        action = self._parse_action(text) or self._parse_action(reasoning)
        if not action:
            # Default: fold if uncertain
            action = Action(player_index=-1, action_type=ActionType.FOLD)

        return AgentDecision(action=action, reasoning=text or reasoning)

    def _parse_action(self, text: str) -> Action | None:
        """Try to parse an action from LLM output text."""
        text_upper = text.upper()

        # Look for explicit action keywords
        if "FOLD" in text_upper:
            return Action(player_index=-1, action_type=ActionType.FOLD)

        # Check for RAISE with amount
        import re

        raise_match = re.search(r"RAISE\s+(?:TO\s+)?(\d+)", text_upper)
        if raise_match:
            return Action(
                player_index=-1,
                action_type=ActionType.RAISE,
                amount=int(raise_match.group(1)),
            )

        # Check for BET
        bet_match = re.search(r"BET\s+(\d+)", text_upper)
        if bet_match:
            return Action(
                player_index=-1,
                action_type=ActionType.BET,
                amount=int(bet_match.group(1)),
            )

        # CALL implies check if no bet to face, or call otherwise
        if "CALL" in text_upper or "CHECK" in text_upper:
            return Action(player_index=-1, action_type=ActionType.CALL)

        return None

    async def _handle_ui_request(self, event: dict) -> None:
        """Auto-respond to pi extension UI requests."""
        if not self._proc or not self._proc.stdin:
            return
        req_id = event.get("id")
        method = event.get("method")

        response = {"type": "extension_ui_response", "id": req_id}

        match method:
            case "confirm":
                response["confirmed"] = True
            case "select":
                response["cancelled"] = True
            case "input":
                response["cancelled"] = True
            case _:
                response["cancelled"] = True

        self._proc.stdin.write(json.dumps(response) + "\n")
        self._proc.stdin.flush()

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
