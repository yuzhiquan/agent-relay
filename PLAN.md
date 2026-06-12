# agent-relay — Build Plan

agent-relay chains independent AI coding CLIs (Claude Code, OpenAI Codex, Gemini
CLI, Aider, or any tool via a generic adapter) into a single pipeline. One agent
plans, another reviews, another implements — with automatic file-based hand-offs
between them and exactly one human approval gate before changes are committed.

## Product Goal

Given a target and a pipeline definition:

```bash
relaypipe run "Add a --json flag to the CLI" -p pipeline.yaml
```

agent-relay should:

- run each step with the configured agent, in order
- pass each step's output file to the next step as input (the hand-off medium)
- stop only at declared approval gates (default: once, before commit)
- support any agent CLI without code changes (generic adapter) or with a small
  adapter class (built-in agents)
- resume cleanly after an interruption via a persisted run journal

## Architecture (three layers)

1. **Agent adapters** (`adapters/`) — one class per CLI implementing
   `build_command(ctx) -> argv`, discovered through a registry. Built-ins:
   `claude`, `codex`, `gemini`, `aider`, `generic`. Third parties register via
   the `agent_relay.adapters` entry-point group.
2. **Config** (`config.py`) — YAML → `Pipeline`/`Step` dataclasses. Steps are
   data, so adding a step or swapping an agent never touches Python.
3. **Runner** (`runner.py`) — executes steps, renders prompts (templating
   `{target}` and `{inputs}`), writes/reads hand-off files, enforces approval
   gates, and journals state to `.agent-relay/state.json` for `--resume`.

The CLI (`cli.py`) wires these together with `run` and `agents` subcommands.

## MVP Scope — status

- [x] Adapter interface + registry + entry-point plugin discovery
- [x] Built-in adapters: claude, codex, gemini, aider, generic
- [x] YAML pipeline config with prompt templates and file hand-offs
- [x] Runner: ordered execution, prompt rendering, approval gates
- [x] State journal + `--resume`
- [x] `--dry-run` (print commands, run nothing) and `--yes` (CI auto-approve)
- [x] CLI: `run`, `agents`
- [x] Tests with mocked agents (no API keys / no network in CI)
- [x] Packaging (pyproject + console script), README, CONTRIBUTING, MIT, CI

## Roadmap (post-MVP)

- [x] **Review loops** — a `loops:` block repeats a contiguous group of steps
  until a verdict marker (`VERDICT: APPROVED`) appears or `max_iterations` is
  hit. Feedback flows via the normal file hand-off. See `runner._run_loop`.
- [x] **`relaypipe new`** — zero-config turnkey: idea → plan → review loop →
  approve-the-plan gate → build into a chosen folder. Embeds default prompts
  (`presets.py`) so no YAML/prompt files are needed. Uses `approve_before` so
  the human gates the *plan* before any code is written.
- **Conditional control flow (more)** — `on_failure: retry`, branching gates
  (`on: review_blockers`), and per-step retry.
- **Structured agent output** — capture JSON (`claude --output-format json`,
  `codex --output-schema`) so gates can branch on machine-readable verdicts.
- **Parallel steps** — fan out independent steps, join before the next.
- **Per-step timeouts, retries, and streaming logs.**
- **Worktree isolation** — run implement steps in a throwaway git worktree.
- **Richer approval UX** — inline diff viewer, commit-message templating, push.
- **`agent-relay init`** — scaffold a pipeline.yaml + prompts interactively.
- **More adapters** — cursor-agent, continue, opencode, ollama-backed tools.

## Design honesty: what this is, and isn't

agent-relay is a **coordination layer**, not an agent. The hard parts —
reasoning, tool use, error recovery — happen *inside* the CLIs it calls. Its
contribution is the glue: ordered hand-offs, a bounded review loop, and one
human gate. Worth being clear-eyed about the limits:

- **It's a thin wrapper.** For a fixed chain, a shell script
  (`claude … > PLAN.md && codex review PLAN.md > review.md && …`) gets you most
  of the way. The real added value is the loop, `--resume`, and YAML config.
- **The hand-off is text-parsed.** Steps coordinate by reading each other's
  output files and matching a `VERDICT:` string. That's brittle: CLI flags and
  output formats change, and we're consuming interfaces never meant for machine
  chaining.
- **The moat is shrinking.** Single-vendor tools increasingly ship this
  natively — subagents, plan-then-approve modes, hooks/slash-commands. The one
  thing they *can't* do is orchestrate a **competitor's** CLI. That cross-vendor
  angle is agent-relay's only durable differentiator.

### v2 direction (highest-leverage moves)

1. **Structured hand-offs over text parsing.** Where a CLI supports it
   (`claude --output-format json`, `codex --output-schema`), capture a
   machine-readable verdict/result instead of grepping for `VERDICT:`. Gates and
   loops branch on a field, not a substring. Falls back to text only when no
   structured mode exists. (Supersedes the "Structured agent output" bullet.)
2. **Lean into cross-vendor.** Treat "plan with Claude, implement with Codex" as
   the headline use case — the capability no native subagent system offers.
   Document mixed-agent recipes; make per-step model/agent selection first-class.
3. **What scripts can't give cheaply.** Per-agent observability, retries, and
   **cost/latency tracking across heterogeneous agents** — the operational layer
   that justifies a tool over a Makefile.

If none of these land, the honest framing is: a clean, well-packaged **design
exploration** of file-based multi-agent hand-offs — valuable as a reference
pattern, not as a tool to depend on.

## Test Plan

- Unit: adapter `build_command` argv for every built-in (roles → flags).
- Unit: generic adapter placeholder substitution and prompt-append fallback.
- Runner: full pipeline runs all steps and threads files between them;
  approval-gate denial aborts; `--resume` skips completed steps; `--dry-run`
  invokes no agent. All via an injected fake agent — no real CLIs.
- CI matrix on Python 3.9 / 3.11 / 3.13 with ruff + pytest.
