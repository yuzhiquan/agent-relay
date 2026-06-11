"""Loop tests: plan->review repeats until approved or the cap is hit."""

from pathlib import Path

import pytest

from agent_relay.adapters import base
from agent_relay.config import Loop, Step, Pipeline
from agent_relay.runner import Runner


@pytest.fixture
def verdict_agent(monkeypatch):
    """Fake agent. The review step emits a verdict controlled by `approve_on`.

    approve_on = the iteration number on which the review should APPROVE.
    Set very high to never approve (forces the loop to its cap).
    """
    state = {"approve_on": 99, "review_calls": 0, "plan_calls": 0}

    class VerdictAgent(base.Agent):
        name = "fake"
        binary = "true"

        def available(self):
            return True

        def build_command(self, ctx):
            return ["true"]

        def run(self, ctx):
            if ctx.role == "review":
                state["review_calls"] += 1
                marker = ("VERDICT: APPROVED" if state["review_calls"] >= state["approve_on"]
                          else "VERDICT: NEEDS_WORK")
                msg = f"review #{state['review_calls']}\n{marker}"
            elif ctx.role == "plan":
                state["plan_calls"] += 1
                msg = f"plan #{state['plan_calls']}"
            else:
                msg = f"{ctx.role} output"
            if ctx.output_file:
                ctx.output_file.parent.mkdir(parents=True, exist_ok=True)
                ctx.output_file.write_text(msg)
            return base.AgentResult(ok=True, stdout=msg, output_file=ctx.output_file)

    monkeypatch.setitem(base._REGISTRY, "fake", VerdictAgent)
    return state


def _loop_pipeline(tmp_path: Path, max_iterations=3):
    return Pipeline(
        name="t",
        workspace=str(tmp_path),
        steps=[
            Step(name="plan", agent="fake", role="plan", prompt="{target}",
                 inputs=["review.md"], output="PLAN.md"),
            Step(name="review", agent="fake", role="review", prompt="{inputs}",
                 inputs=["PLAN.md"], output="review.md"),
            Step(name="implement", agent="fake", role="implement",
                 prompt="{inputs}", inputs=["PLAN.md"]),
        ],
        loops=[Loop(name="plan-loop", steps=["plan", "review"],
                    max_iterations=max_iterations, until_step="review")],
    )


def test_loop_stops_early_on_approval(tmp_path, verdict_agent):
    verdict_agent["approve_on"] = 2          # approve on the 2nd review
    runner = Runner(_loop_pipeline(tmp_path, max_iterations=5), target="x")
    result = runner.run()
    assert not result.aborted
    assert verdict_agent["review_calls"] == 2   # stopped early, not 5
    assert verdict_agent["plan_calls"] == 2


def test_loop_runs_to_cap_when_never_approved(tmp_path, verdict_agent):
    verdict_agent["approve_on"] = 99         # never approves
    runner = Runner(_loop_pipeline(tmp_path, max_iterations=3), target="x")
    result = runner.run()
    assert not result.aborted                # cap reached, continues anyway
    assert verdict_agent["review_calls"] == 3
    assert verdict_agent["plan_calls"] == 3


def test_implement_runs_after_loop(tmp_path, verdict_agent):
    verdict_agent["approve_on"] = 1
    runner = Runner(_loop_pipeline(tmp_path), target="x")
    result = runner.run()
    # implement ran once after the loop converged
    assert not result.aborted
    assert "review #1" in (tmp_path / "review.md").read_text()
