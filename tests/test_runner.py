"""Runner tests using a fake agent injected via the registry."""

from pathlib import Path

import pytest

from agent_relay.adapters import base
from agent_relay.config import Pipeline
from agent_relay.runner import Runner


@pytest.fixture
def fake_agent(monkeypatch):
    """Register a fake agent that writes its output file and succeeds."""

    calls = []

    class FakeAgent(base.Agent):
        name = "fake"
        binary = "true"

        def available(self):
            return True

        def build_command(self, ctx):
            return ["true"]

        def run(self, ctx):
            calls.append(ctx)
            if ctx.output_file:
                ctx.output_file.parent.mkdir(parents=True, exist_ok=True)
                ctx.output_file.write_text(f"output of {ctx.role}")
            return base.AgentResult(ok=True, stdout="ok", output_file=ctx.output_file)

    monkeypatch.setitem(base._REGISTRY, "fake", FakeAgent)
    return calls


def _pipeline(tmp_path: Path, approve_after=False):
    return Pipeline(
        name="t",
        workspace=str(tmp_path),
        steps=[
            base_step("plan", "PLAN.md", inputs=[]),
            base_step("impl", None, inputs=["PLAN.md"], approve=approve_after),
        ],
    )


def base_step(name, output, inputs, approve=False):
    from agent_relay.config import Step

    return Step(name=name, agent="fake", role=name, prompt="{target}",
                inputs=inputs, output=output, approve_after=approve)


def test_pipeline_runs_all_steps_and_passes_files(tmp_path, fake_agent):
    runner = Runner(_pipeline(tmp_path), target="build X")
    result = runner.run()
    assert not result.aborted
    assert (tmp_path / "PLAN.md").read_text() == "output of plan"
    # second step's prompt should include the first step's file content
    second_ctx = fake_agent[1]
    assert "output of plan" in second_ctx.prompt


def test_approval_gate_blocks_when_denied(tmp_path, fake_agent):
    p = _pipeline(tmp_path, approve_after=True)
    runner = Runner(p, target="x", approval_fn=lambda name, res: False)
    result = runner.run()
    assert result.aborted


def test_resume_skips_completed_steps(tmp_path, fake_agent):
    runner = Runner(_pipeline(tmp_path), target="x")
    runner.run()
    # second run with resume should skip both (state recorded them)
    calls_before = len(fake_agent)
    runner2 = Runner(_pipeline(tmp_path), target="x")
    runner2.run(resume=True)
    assert len(fake_agent) == calls_before  # no new agent calls


def test_dry_run_invokes_no_agent(tmp_path, fake_agent):
    runner = Runner(_pipeline(tmp_path), target="x", dry_run=True)
    runner.run()
    assert len(fake_agent) == 0
