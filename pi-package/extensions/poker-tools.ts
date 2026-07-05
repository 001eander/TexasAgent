/**
 * TexasAgent — Poker Tools Extension for pi
 *
 * Registers 6 poker tools for LLM agent use:
 *   poker_equity        — Monte Carlo equity calculation
 *   poker_hand_strength — Evaluate current hand rank
 *   poker_pot_odds      — Calculate pot odds and required equity
 *   poker_opponent_stats — Query opponent VPIP/PFR/AF stats
 *   poker_range_analysis — Range vs range equity
 *   poker_solve         — GTO solver (TexasSolver bridge)
 */

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const execFileAsync = promisify(execFile);

// Path to Python scripts relative to this package
const SCRIPTS_DIR = new URL("../scripts", import.meta.url).pathname;

interface PyEquityResult {
  win: number;
  tie: number;
  lose: number;
  equity: number;
}

async function runPythonEquity(args: string[]): Promise<PyEquityResult> {
  const { stdout } = await execFileAsync("python3", [
    `${SCRIPTS_DIR}/equity.py`,
    ...args,
  ]);
  return JSON.parse(stdout);
}

export default function (pi: ExtensionAPI) {
  // ── poker_equity ──────────────────────────────────────────
  pi.registerTool({
    name: "poker_equity",
    label: "Poker Equity",
    description:
      "Calculate win/tie/lose probabilities for a Texas Hold'em hand " +
      "using Monte Carlo simulation. Provide your hole cards, optional " +
      "community cards, and number of opponents.",
    promptSnippet: "Calculate Monte Carlo equity for poker hand",
    promptGuidelines: [
      "Use poker_equity to estimate your hand's chance of winning against N opponents.",
      "Call poker_equity before making close decisions on the flop or turn.",
    ],
    parameters: Type.Object({
      hole_cards: Type.Array(Type.String(), {
        description: "Your hole cards, e.g. ['Ah', 'Kh']",
      }),
      community_cards: Type.Optional(
        Type.Array(Type.String(), {
          description: "Community cards on board, e.g. ['Qd', 'Jd', '9c']",
        })
      ),
      num_opponents: Type.Optional(
        Type.Number({ description: "Number of opponents (default 1)" })
      ),
      num_simulations: Type.Optional(
        Type.Number({
          description: "Number of Monte Carlo trials (default 5000, max 20000)",
        })
      ),
    }),
    async execute(_toolCallId, params, _signal, onUpdate) {
      onUpdate?.({
        content: [{ type: "text", text: "Running Monte Carlo simulation..." }],
      });

      const hole = params.hole_cards as string[];
      const community = (params.community_cards as string[] | undefined) ?? [];
      const opponents = (params.num_opponents as number) ?? 1;
      const sims = Math.min((params.num_simulations as number) ?? 5000, 20000);

      const result = await runPythonEquity([
        "--hole",
        ...hole,
        "--community",
        ...community,
        "--opponents",
        String(opponents),
        "--sims",
        String(sims),
      ]);

      return {
        content: [
          {
            type: "text",
            text: [
              `**Equity vs ${opponents} opponent(s):**`,
              `- Win: ${(result.win * 100).toFixed(1)}%`,
              `- Tie: ${(result.tie * 100).toFixed(1)}%`,
              `- Lose: ${(result.lose * 100).toFixed(1)}%`,
              `- Total Equity: ${(result.equity * 100).toFixed(1)}%`,
            ].join("\n"),
          },
        ],
        details: result,
      };
    },
  });

  // ── poker_hand_strength ───────────────────────────────────
  pi.registerTool({
    name: "poker_hand_strength",
    label: "Hand Strength",
    description:
      "Evaluate current hand strength (High Card, Pair, Two Pair, etc.) " +
      "given hole cards and community cards.",
    promptSnippet: "Evaluate poker hand strength category",
    parameters: Type.Object({
      hole_cards: Type.Array(Type.String(), {
        description: "Your hole cards, e.g. ['Ah', 'Kh']",
      }),
      community_cards: Type.Array(Type.String(), {
        description: "Community cards on board, e.g. ['Qd', 'Jd', '9c']",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate) {
      const hole = params.hole_cards as string[];
      const community = (params.community_cards as string[]) ?? [];

      const { stdout } = await execFileAsync("python3", [
        `${SCRIPTS_DIR}/hand_strength.py`,
        "--hole",
        ...hole,
        "--community",
        ...community,
      ]);
      const result = JSON.parse(stdout);

      return {
        content: [
          {
            type: "text",
            text:
              result.made_hand === "incomplete"
                ? `Hand incomplete — need ${5 - (hole.length + community.length)} more cards.`
                : `**Made Hand:** ${result.made_hand} (category ${result.category}/9)`,
          },
        ],
        details: result,
      };
    },
  });

  // ── poker_pot_odds ────────────────────────────────────────
  pi.registerTool({
    name: "poker_pot_odds",
    label: "Pot Odds",
    description:
      "Calculate pot odds and the minimum equity required to call a bet.",
    promptSnippet: "Calculate pot odds and required equity",
    promptGuidelines: [
      "Use poker_pot_odds to determine if you have the right price to call a draw.",
      "Compare the required equity from pot odds with your actual equity from poker_equity.",
    ],
    parameters: Type.Object({
      pot: Type.Number({ description: "Current pot size (before your call)" }),
      to_call: Type.Number({ description: "Amount you need to call" }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate) {
      const pot = params.pot as number;
      const toCall = params.to_call as number;

      if (toCall === 0) {
        return {
          content: [
            {
              type: "text",
              text: "No cost to check. You can see the next card for free.",
            },
          ],
          details: { pot_odds: 0, required_equity: 0 },
        };
      }

      const requiredEquity = toCall / (pot + toCall);
      const potOdds = pot / toCall;

      return {
        content: [
          {
            type: "text",
            text: [
              `**Pot:** ${pot}  |  **To Call:** ${toCall}`,
              `- Pot odds: **${potOdds.toFixed(1)}:1**`,
              `- Required equity: **${(requiredEquity * 100).toFixed(1)}%**`,
              ``,
              requiredEquity < 0.33
                ? "Good price — only need ~33% equity to break even."
                : requiredEquity > 0.5
                  ? "Expensive — need >50% equity. Only call with strong made hands."
                  : "Marginal — need solid equity to profitably call.",
            ].join("\n"),
          },
        ],
        details: {
          pot_odds: potOdds,
          required_equity: requiredEquity,
        },
      };
    },
  });

  // ── poker_opponent_stats ──────────────────────────────────
  pi.registerTool({
    name: "poker_opponent_stats",
    label: "Opponent Stats",
    description:
      "Get opponent statistics: VPIP (Voluntarily Put money In Pot), " +
      "PFR (Preflop Raise), 3-bet%, c-bet%, aggression factor.",
    promptSnippet: "Query opponent poker statistics (VPIP/PFR/AF)",
    promptGuidelines: [
      "Use poker_opponent_stats to profile opponents before making decisions.",
      "High VPIP + low PFR = loose-passive (call too much, exploit by value betting).",
      "Low VPIP + high PFR = tight-aggressive (respect their raises, bluff more).",
    ],
    parameters: Type.Object({
      player_name: Type.String({
        description: "Name of the opponent to look up",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate) {
      const name = params.player_name as string;
      // In-memory stub — real implementation queries SQLite
      const stub = {
        player_name: name,
        hands: 0,
        vpip: 0,
        pfr: 0,
        three_bet: 0,
        cbet: 0,
        aggression_factor: 0,
        note: "No stats available yet — opponent hasn't been tracked in this session.",
      };

      return {
        content: [
          {
            type: "text",
            text:
              stub.hands === 0
                ? `**${name}:** No tracked hands yet.`
                : [
                    `**${name}** (${stub.hands} hands):`,
                    `- VPIP: ${stub.vpip}% | PFR: ${stub.pfr}% | 3-bet: ${stub.three_bet}%`,
                    `- C-bet: ${stub.cbet}% | AF: ${stub.aggression_factor}`,
                  ].join("\n"),
          },
        ],
        details: stub,
      };
    },
  });

  // ── poker_range_analysis ──────────────────────────────────
  pi.registerTool({
    name: "poker_range_analysis",
    label: "Range Analysis",
    description:
      "Analyze a hand range against a board — determine range advantage, " +
      "equity distribution, and best candidates to continue.",
    promptSnippet: "Analyze poker hand range vs board",
    parameters: Type.Object({
      range_description: Type.String({
        description:
          "Range description, e.g. 'UTG open: 77+, ATs+, AJo+, KQs, QJs, JTs'",
      }),
      board: Type.Array(Type.String(), {
        description: "Community cards, e.g. ['Qd', 'Jd', '9c']",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate) {
      const desc = params.range_description as string;
      const board = (params.board as string[]).join(" ");

      return {
        content: [
          {
            type: "text",
            text: [
              `**Range:** ${desc}`,
              `**Board:** ${board}`,
              ``,
              `Range analysis requires parsing range notation (e.g., "ATs+", "77+").`,
              `For now, use poker_equity with specific hands to evaluate matchups.`,
              `Full range vs range analysis with the solver will be available in a future version.`,
            ].join("\n"),
          },
        ],
        details: { range: desc, board },
      };
    },
  });

  // ── poker_solve ───────────────────────────────────────────
  pi.registerTool({
    name: "poker_solve",
    label: "GTO Solver",
    description:
      "Run the GTO solver (TexasSolver) to find game-theory optimal strategies " +
      "for a specific poker situation. Requires TexasSolver to be installed.",
    promptSnippet: "Solve for GTO strategy at current decision point",
    promptGuidelines: [
      "Use poker_solve for complex postflop spots where you need exact GTO frequencies.",
      "poker_solve is computationally expensive — prefer poker_equity for simpler spots.",
    ],
    parameters: Type.Object({
      board: Type.Array(Type.String(), {
        description: "Community cards, e.g. ['Qd', 'Jd', '9c']",
      }),
      pot: Type.Number({ description: "Current pot size" }),
      effective_stack: Type.Number({ description: "Effective stack size" }),
      hero_range: Type.String({
        description: "Hero's range, e.g. 'AKs, AKo, QQ+, JTs'",
      }),
      villain_range: Type.Optional(
        Type.String({
          description: "Villain's estimated range (default: any two)",
        })
      ),
    }),
    async execute(_toolCallId, params, _signal, onUpdate) {
      onUpdate?.({
        content: [
          {
            type: "text",
            text: "GTO solver not yet configured. Install TexasSolver and set TEXAS_SOLVER_PATH.",
          },
        ],
      });

      return {
        content: [
          {
            type: "text",
            text: [
              "**GTO Solver:** Not configured.",
              "",
              "To enable GTO solving:",
              "1. Install TexasSolver from https://github.com/bupticybee/TexasSolver",
              "2. Set the `TEXAS_SOLVER_PATH` environment variable",
              "3. Restart the agent",
              "",
              "For now, use `poker_equity` and `poker_pot_odds` for decision support.",
            ].join("\n"),
          },
        ],
        details: { status: "not_configured" },
      };
    },
  });

  pi.on("session_start", () => {
    // Future: initialize opponent tracking database
  });
}
