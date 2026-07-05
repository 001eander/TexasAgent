"""Pi RPC client — async subprocess wrapper for pi coding agent.

Communicates with pi in headless RPC mode via stdin/stdout JSON.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass

from app.engine.types import Action, ActionType

logger = logging.getLogger(__name__)


@dataclass
class PiRpcConfig:
    pi_path: str = "pi"
    model: str = "deepseek/deepseek-v4-pro"
    extension_path: str | None = None
    thinking_level: str = "medium"
    startup_timeout: float = 30.0
    decide_timeout: float = 60.0


@dataclass
class AgentDecision:
    action: Action | None
    reasoning: str = ""


class PiRpcClient:
    """Async client for pi RPC mode."""

    def __init__(self, config: PiRpcConfig | None = None):
        self.config = config or PiRpcConfig()
        self._proc: asyncio.subprocess.Process | None = None
        self._ready = False

    async def start(self) -> None:
        """Spawn pi in RPC mode and wait for it to be ready."""
        args = [
            self.config.pi_path,
            "--mode",
            "rpc",
            "--no-session",
            "--model",
            self.config.model,
        ]
        if self.config.extension_path:
            args.extend(["-e", self.config.extension_path])

        env = os.environ.copy()

        logger.info(f"Starting pi RPC: {' '.join(args)}")
        self._proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._ready = True
        logger.info(f"pi RPC started (pid={self._proc.pid})")

    async def stop(self) -> None:
        """Terminate the pi subprocess."""
        if self._proc:
            self._ready = False
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
            self._proc = None
            logger.info("pi RPC stopped")

    async def decide(self, prompt: str) -> AgentDecision:
        """Send game state to pi, wait for LLM to decide, return action."""
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            return AgentDecision(action=None, reasoning="pi RPC not running")

        # Send prompt
        cmd = json.dumps({"type": "prompt", "message": prompt}) + "\n"
        self._proc.stdin.write(cmd.encode())
        await self._proc.stdin.drain()

        reasoning_parts: list[str] = []
        final_text: list[str] = []

        try:
            async with asyncio.timeout(self.config.decide_timeout):
                while True:
                    line = await self._proc.stdout.readline()
                    if not line:
                        break

                    try:
                        event = json.loads(line.decode())
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("type", "")

                    if etype == "message_update":
                        delta = event.get("assistantMessageEvent", {})
                        dtype = delta.get("type", "")
                        if dtype == "text_delta":
                            final_text.append(delta.get("delta", ""))
                        elif dtype == "thinking_delta":
                            reasoning_parts.append(delta.get("thinking", ""))

                    elif etype == "tool_execution_start":
                        tname = event.get("toolName", "unknown")
                        logger.info(f"pi tool: {tname}")

                    elif etype == "tool_execution_end":
                        tname = event.get("toolName", "unknown")
                        is_err = event.get("isError", False)
                        logger.info(
                            f"pi tool done: {tname} {'(error)' if is_err else ''}"
                        )

                    elif etype == "agent_end":
                        break

                    elif etype == "extension_ui_request":
                        await self._auto_respond(event)

        except asyncio.TimeoutError:
            logger.warning("pi decision timed out")
            return AgentDecision(action=None, reasoning="timeout")

        reasoning = "".join(reasoning_parts)
        text = "".join(final_text)

        action = _parse_action(text)
        if not action:
            action = _parse_action(reasoning)

        return AgentDecision(action=action, reasoning=text or reasoning)

    async def _auto_respond(self, event: dict) -> None:
        """Auto-answer pi extension UI prompts."""
        if not self._proc or not self._proc.stdin:
            return
        req_id = event.get("id")
        method = event.get("method", "")
        resp = {"type": "extension_ui_response", "id": req_id}

        if method == "confirm":
            resp["confirmed"] = True
        else:
            resp["cancelled"] = True

        self._proc.stdin.write((json.dumps(resp) + "\n").encode())
        await self._proc.stdin.drain()

    @property
    def is_running(self) -> bool:
        return self._ready and self._proc is not None and self._proc.returncode is None


def _parse_action(text: str) -> Action | None:
    """Extract poker action from LLM output text."""
    if not text:
        return None
    upper = text.upper()

    # FOLD
    if re.search(r"\bFOLD\b", upper):
        return Action(player_index=-1, action_type=ActionType.FOLD)

    # ALL-IN
    if re.search(r"\bALL[-\s]?IN\b", upper):
        return Action(player_index=-1, action_type=ActionType.ALL_IN, amount=0)

    # RAISE <amount> or RAISE TO <amount>
    m = re.search(r"RAISE\s+(?:TO\s+)?(\d+)", upper)
    if m:
        return Action(
            player_index=-1, action_type=ActionType.RAISE, amount=int(m.group(1))
        )

    # BET <amount>
    m = re.search(r"\bBET\s+(\d+)", upper)
    if m:
        return Action(
            player_index=-1, action_type=ActionType.BET, amount=int(m.group(1))
        )

    # CALL or CHECK
    if re.search(r"\b(?:CALL|CHECK)\b", upper):
        return Action(player_index=-1, action_type=ActionType.CALL)

    return None
