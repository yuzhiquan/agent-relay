You are the implementation agent working on the **agent-relay** project itself.

Implement the `agent-relay init` command according to the build spec below
(produced by the reviewer), staying consistent with the existing codebase:

- Add `cmd_init` to `src/agent_relay/cli.py` and register an `init` subparser in
  `build_parser`.
- Generate a starter `pipeline.yaml` and `prompts/` directory matching the
  schema used in `examples/pipeline.yaml`.
- Support both interactive prompts and non-interactive defaults (so `--yes`
  works in CI). Never overwrite existing files without an explicit `--force`.
- Add tests in `tests/` using the existing mocked-agent style — do not invoke
  real agent CLIs or the network.

Run `pytest -q` to confirm everything passes.

IMPORTANT: Do NOT commit, push, or create branches. Leave changes in the working
tree for human review. When done, summarize exactly what you changed.

PLAN AND BUILD SPEC:
{inputs}
