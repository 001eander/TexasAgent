---
name: poker-strategy
description: Texas Hold'em poker strategy — GTO fundamentals, position play, bet sizing, opponent exploitation. Use when playing poker or making betting decisions.
---

# Texas Hold'em Strategy Reference

## Core GTO Principles

### Position
Position is the most important factor in poker. Play more hands in late position (BTN, CO), fewer in early position (UTG).

| Position | Abbr | Opening Range (6-max) |
|----------|------|----------------------|
| Button | BTN | ~40% of hands |
| Cutoff | CO | ~25% |
| Hijack | HJ | ~20% |
| Lojack | LJ | ~16% |
| UTG | UTG | ~13% |

### Preflop Hand Categories
- **Premium:** AA, KK, QQ, AKs — 3-bet/4-bet aggressively
- **Strong:** JJ, TT, AKo, AQs — open from any position
- **Speculative:** Small pairs, suited connectors — play in position, fold to large raises
- **Trash:** Everything else — fold preflop unless in blinds

### Bet Sizing Guidelines
- **Preflop open:** 2.5–3x BB (add 1BB per limper)
- **3-bet:** 3–4x the open raise in position, 4–5x out of position
- **C-bet flop:** 33–75% pot depending on board texture
- **Turn bet:** 66–100% pot with strong hands and draws
- **River value bet:** 50–75% pot

### Continuation Bet (C-bet)
- C-bet more on dry boards (K72r), less on wet boards (JTs9)
- In position: c-bet ~65-70% of flops
- Out of position: c-bet ~50% of flops, mostly on favorable boards

## Tool Usage Strategy

### When to call `poker_equity`
- On the flop with a draw — calculate if you have odds to continue
- Before calling an all-in — confirm you have the required equity
- With marginal made hands — evaluate vs opponent's likely range

### When to call `poker_pot_odds`
- Facing any bet — always calculate pot odds
- Compare required equity with your actual equity from `poker_equity`
- Rule of thumb: need 33% equity to call a pot-sized bet, 25% for half-pot

### When to call `poker_solve` (if configured)
- Complex river spots where you need exact GTO bluff/value frequencies
- 3-bet and 4-bet pot postflop situations
- When studying specific spots (not during live play — solver is slow)

### When to call `poker_opponent_stats`
- Before making a big decision against a specific opponent
- Stats guide exploitation:
  - **High VPIP (>35%), Low PFR (<15%):** Loose-passive. Value bet relentlessly, don't bluff.
  - **Low VPIP (<20%), High PFR (>20%):** Tight-aggressive. Respect raises, bluff more postflop.
  - **High 3-bet (>10%):** 4-bet wider for value, call less.
  - **High fold-to-cbet (>60%):** C-bet almost always.

## Exploitation Heuristics

### Against Loose-Passive (Calling Station)
- Never bluff — they won't fold
- Bet larger for value (75-100% pot)
- Check back marginal hands

### Against Tight-Aggressive (Nit/Reg)
- Bluff more on scary boards (A-high, flush completing)
- Fold to their raises unless you have a strong hand
- Steal blinds aggressively

### Against Maniac (Aggressive-Fish)
- Trap with strong hands — let them bluff into you
- Call down lighter — they bluff too much
- Don't try to bluff them — they don't fold

## Decision Output Format

When asked to decide, output:
1. Brief situation analysis (1-2 sentences)
2. Tool calls as needed (equity, pot odds, opponent stats)
3. Final decision: FOLD / CALL / RAISE <amount> with brief reasoning
