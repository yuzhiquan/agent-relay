"""CLI tests, including the --max-iterations loop-cap override."""

import textwrap
from pathlib import Path

import pytest

from agent_relay.adapters import base
from agent_relay.cli import main


@pytest.fixture
def verdict_agent(monkeypatch):
    """Fake 'fake' agent; review never approves so loops run to their cap."""
    state = {"review_calls": 0}

    class FakeAgent(base.Agent):
        name = "fake"
        binary = "true"

        def available(self):
            return True

        def build_command(self, ctx):
            return ["true"]

        def run(self, ctx):
            if ctx.role == "review":
                state["review_calls"] += 1
            msg = "VERDICT: NEEDS_WORK"
            if ctx.output_file:
                ctx.output_file.parent.mkdir(parents=True, exist_ok=True)
                ctx.output_file.write_text(msg)
            return base.AgentResult(ok=True, stdout=msg, output_file=ctx.output_file)

    monkeypatch.setitem(base._REGISTRY, "fake", FakeAgent)
    return state


def _write_pipeline(tmp_path: Path, max_iterations: int) -> Path:
    yaml = textwrap.dedent(f"""
        name: t
        workspace: {tmp_path}
        steps:
          - name: plan
            agent: fake
            role: plan
            prompt: "{{target}}"
            output: PLAN.md
          - name: review
            agent: fake
            role: review
            prompt: "{{inputs}}"
            inputs: [PLAN.md]
            output: review.md
        loops:
          - name: plan-review
            steps: [plan, review]
            until_step: review
            max_iterations: {max_iterations}
    """)
    p = tmp_path / "pipeline.yaml"
    p.write_text(yaml)
    return p


def test_cli_uses_pipeline_cap_by_default(tmp_path, verdict_agent):
    p = _write_pipeline(tmp_path, max_iterations=2)
    rc = main(["run", "x", "-p", str(p), "--yes"])
    assert rc == 0
    assert verdict_agent["review_calls"] == 2


def test_max_iterations_flag_overrides_pipeline(tmp_path, verdict_agent):
    p = _write_pipeline(tmp_path, max_iterations=2)
    rc = main(["run", "x", "-p", str(p), "--yes", "--max-iterations", "4"])
    assert rc == 0
    assert verdict_agent["review_calls"] == 4   # override beat the YAML's 2


def test_max_iterations_must_be_positive(tmp_path, verdict_agent):
    p = _write_pipeline(tmp_path, max_iterations=2)
    rc = main(["run", "x", "-p", str(p), "--yes", "--max-iterations", "0"])
    assert rc == 2
    assert verdict_agent["review_calls"] == 0   # bailed before running
