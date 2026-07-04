# TexasAgent

LLM-powered Texas Hold'em poker AI agent. Uses pi coding agent for LLM reasoning + tool calling (equity calculator, GTO solver, opponent tracking), with a FastAPI web UI for interactive gameplay.

## Architecture

```
Frontend (Web UI) ←→ FastAPI (Python) ←→ pi RPC (Node.js/LLM)
                          │
                    Poker Engine
                    Tool Layer
                    Database
```
