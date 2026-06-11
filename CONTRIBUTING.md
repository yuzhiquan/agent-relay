# Contributing to agent-relay

Thanks for helping! The most common contribution is **a new agent adapter**.

## Add an adapter

1. Create `src/agent_relay/adapters/<tool>.py`:

   ```python
   from .base import Agent, AgentContext, register

   @register
   class ToolAgent(Agent):
       name = "tool"          # the key used in pipeline.yaml
       binary = "tool"        # the executable on PATH

       def build_command(self, ctx: AgentContext) -> list[str]:
           cmd = [self.binary, "--prompt", ctx.prompt]
           if ctx.output_file:
               cmd += ["--out", str(ctx.output_file)]
           if ctx.model:
               cmd += ["--model", ctx.model]
           return cmd + ctx.extra_args
   ```

2. Import it in `src/agent_relay/adapters/__init__.py` so it registers.
3. Add a test in `tests/test_adapters.py` (no real CLI — assert the argv).

Adapters should be **non-interactive** and **must not commit/push** — the human
gate owns that decision. Map the `implement` role to the tool's
auto-apply-but-don't-commit mode.

## Ship an adapter as a separate package

Register the entry point in your own `pyproject.toml`:

```toml
[project.entry-points."agent_relay.adapters"]
tool = "my_pkg.adapter"
```

agent-relay discovers it at startup. No fork required.

## Dev setup

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
