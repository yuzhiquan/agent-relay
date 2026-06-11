You are the planning agent working on the **agent-relay** project itself.

Below is the project's own PLAN.md. From its "Roadmap (post-MVP)" section, focus
on this item:

  > **`agent-relay init`** — scaffold a pipeline.yaml + prompts interactively.

Write a focused, concrete build spec for implementing `agent-relay init`,
grounded in the existing structure (a `cmd_init` in `src/agent_relay/cli.py`
wired into `build_parser`; generates a starter `pipeline.yaml` + `prompts/`
matching `examples/pipeline.yaml`; interactive with non-interactive defaults;
never overwrites without `--force`; tests in the mocked-agent style).

If a prior review is included below, REVISE the spec to address every point the
reviewer raised. Output ONLY the spec as markdown.

PROJECT PLAN AND ANY PRIOR REVIEW:
{inputs}
