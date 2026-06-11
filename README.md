# agent-relay

**Chain any AI coding CLIs into an approve-once pipeline.**

You give a target. One agent plans, another reviews the plan, another implements
it — automatically, with no copy-pasting between them. The only time it stops for
you is the final gate, right before anything is committed.

```
  target ─▶ ┌──────┐   PLAN.md   ┌────────┐  review.md  ┌──────────┐   ⏸ you
            │ plan │ ──────────▶ │ review │ ──────────▶ │ implement│ ─────▶ commit?
            └──────┘             └────────┘             └──────────┘
            (claude)              (codex)                 (codex)
```

Each arrow is an automatic hand-off; files on disk are the medium. Swap any box
for a different agent by changing one line of YAML.

## Why

Running a multi-agent workflow by hand means copy-pasting one tool's output into
the next, over and over. Add a third agent and the transfers multiply.
agent-relay makes the hand-offs automatic and gates only the decision that
actually needs a human.

## Supported agents

Built-in adapters: **claude** (Claude Code), **codex** (OpenAI Codex),
**gemini** (Gemini CLI), **aider**, and **generic** — wrap *any* CLI from YAML
with no code:

```yaml
- name: implement
  agent: generic
  command: ["mytool", "run", "--prompt", "{prompt}", "--out", "{output}"]
```

Placeholders: `{prompt} {output} {workspace} {model} {role}`.

## Install

```bash
pipx install agent-relay         # once published
# or, from source:
pip install -e ".[dev]"
```

## Quick start: idea → project (zero config)

The fastest path. Give an idea and a folder; agent-relay plans, loops the plan
through review until it's solid, shows you the **final plan**, and — once you
approve — builds the project into that folder. No YAML, no prompt files:

```bash
agent-relay new "a todo-list CLI in Rust with JSON persistence" -d ./todo-cli
```

What happens:

1. **plan** — an agent drafts a build plan
2. **review loop** — a reviewer critiques it; the plan is revised and re-reviewed
   until `VERDICT: APPROVED` or the loop cap (default 3) is hit
3. **⏸ you approve** — the final plan is printed; answer `y` to build
4. **build** — the project is created in `./todo-cli`

Useful options:

```bash
agent-relay new "..." -d ./app --agent codex          # use Codex to plan+review+build
agent-relay new "..." -d ./app --agent claude --build-agent codex   # mix agents
agent-relay new "..." -d ./app --max-iterations 5     # allow more review rounds
agent-relay new "..." -d ./app --dry-run              # preview the commands
agent-relay new "..." -d ./app --yes                  # CI: skip the approval prompt
```

For full control over steps, agents, and gates, write a pipeline (below) and use
`agent-relay run`.

## Use

```bash
# list available agents
agent-relay agents

# run the example pipeline
agent-relay run "Add a --json flag to the CLI" -p examples/pipeline.yaml

# preview commands without running anything
agent-relay run "..." -p examples/pipeline.yaml --dry-run

# resume an interrupted run
agent-relay run --resume -p examples/pipeline.yaml

# CI mode: auto-approve every gate
agent-relay run "..." -p pipeline.yaml --yes

# override the loop cap for this run (beats max_iterations in the YAML)
agent-relay run "..." -p pipeline.yaml --max-iterations 5
```

## Example: agent-relay improving itself

The repo ships a **self-hosted** pipeline that points agent-relay at its own
codebase. It reads this project's [`PLAN.md`](PLAN.md), has one agent review a
roadmap item (`agent-relay init`), and has another implement it — pausing once
for your approval before you commit:

```bash
# preview the chain (reads PLAN.md, no API calls)
agent-relay run -p examples/self-hosted/pipeline.yaml --dry-run

# run it for real
agent-relay run -p examples/self-hosted/pipeline.yaml
```

The goal is baked into the prompts, so no positional target is needed — the
plan file *is* the input. This is the best worked example of the
"review an existing plan → implement" flow: see
[`examples/self-hosted/`](examples/self-hosted/).

## Pipeline config

```yaml
name: plan-review-implement
workspace: .
steps:
  - name: plan
    agent: claude
    role: plan                  # plan | review | implement | generic
    prompt_file: prompts/plan.md
    output: PLAN.md             # what this agent writes

  - name: review-plan
    agent: codex
    role: review
    inputs: [PLAN.md]           # files fed into the prompt ({inputs})
    output: .agent-relay/plan-review.md

  - name: implement
    agent: codex
    role: implement
    inputs: [PLAN.md, .agent-relay/plan-review.md]
    approve_after: true         # the single human gate
```

## Review loops (iterate up to a cap)

One plan→review pass is rarely enough. A `loops:` block repeats a contiguous
group of steps until a reviewer approves — or a hard iteration cap is hit, so it
never spins forever:

```yaml
steps:
  - name: plan
    agent: claude
    role: plan
    inputs: [PLAN.md, .agent-relay/review.md]   # sees last round's feedback
    output: PLAN.md
  - name: review
    agent: codex
    role: review
    inputs: [PLAN.md]
    output: .agent-relay/review.md
  - name: implement
    agent: codex
    role: implement
    inputs: [PLAN.md]
    approve_after: true

loops:
  - name: plan-review
    steps: [plan, review]            # must be contiguous & in pipeline order
    until_step: review               # whose output holds the verdict
    max_iterations: 3                # the cap (override per-run with --max-iterations)
    approved_marker: "VERDICT: APPROVED"
```

How it stops:

- The **review prompt** is told to end its output with `VERDICT: APPROVED` or
  `VERDICT: NEEDS_WORK`. The runner reads the verdict step's output:
  approved → exit the loop early; otherwise → re-run the group.
- The feedback path is the normal file hand-off: list the review's `output` as
  an `input` of the first step, so the next pass sees the last review.
- If the cap is reached without approval, the run logs `🛑 hit max_iterations`
  and proceeds to the next step anyway (the human gate still backstops it).

The self-hosted example uses exactly this — see
[`examples/self-hosted/pipeline.yaml`](examples/self-hosted/pipeline.yaml).

## Adding a new agent

Two ways:

1. **No code** — use the `generic` adapter with a `command:` template (above).
2. **An adapter class** — ~20 lines:

   ```python
   from agent_relay.adapters.base import Agent, AgentContext, register

   @register
   class MyToolAgent(Agent):
       name = "mytool"
       binary = "mytool"

       def build_command(self, ctx: AgentContext) -> list[str]:
           cmd = [self.binary, "--prompt", ctx.prompt]
           if ctx.output_file:
               cmd += ["--out", str(ctx.output_file)]
           return cmd
   ```

   Ship it as a separate package by registering the
   `agent_relay.adapters` entry point — no fork needed.

## Development

```bash
pip install -e ".[dev]"
pytest          # tests use mocked agents — no API keys needed
ruff check .
```

## License

MIT — see [LICENSE](LICENSE).
