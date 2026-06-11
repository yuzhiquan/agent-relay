"""Tests for the zero-config `agent-relay new` flow and approve_before gate."""

import pytest

from agent_relay.adapters import base
from agent_relay.cli import main


@pytest.fixture
def building_agent(monkeypatch):
    """Fake agent: review approves immediately; build writes a project file."""
    state = {"roles": []}

    class FakeAgent(base.Agent):
        name = "fake"
        binary = "true"

        def available(self):
            return True

        def build_command(self, ctx):
            return ["true"]

        def run(self, ctx):
            state["roles"].append(ctx.role)
            if ctx.role == "review":
                msg = "looks good\nVERDICT: APPROVED"
            elif ctx.role == "implement":
                # Simulate creating the project in the workspace.
                (ctx.workspace / "main.py").write_text("print('hi')\n")
                msg = "created main.py"
            else:
                msg = "PLAN: build the thing"
            if ctx.output_file:
                ctx.output_file.parent.mkdir(parents=True, exist_ok=True)
                ctx.output_file.write_text(msg)
            return base.AgentResult(ok=True, stdout=msg, output_file=ctx.output_file)

    monkeypatch.setitem(base._REGISTRY, "fake", FakeAgent)
    return state


def test_new_builds_project_after_approval(tmp_path, building_agent):
    proj = tmp_path / "myproj"
    rc = main(["new", "a todo CLI", "-d", str(proj),
               "--agent", "fake", "--yes"])
    assert rc == 0
    # plan -> review (approved) -> build
    assert building_agent["roles"] == ["plan", "review", "implement"]
    assert (proj / "PLAN.md").exists()
    assert (proj / "main.py").read_text() == "print('hi')\n"
    # preset prompts were materialized
    assert (proj / ".agent-relay" / "prompts" / "plan.md").exists()


def test_new_aborts_when_plan_rejected(tmp_path, building_agent, monkeypatch):
    # Decline at the build gate.
    monkeypatch.setattr("builtins.input", lambda _: "n")
    proj = tmp_path / "p2"
    rc = main(["new", "idea", "-d", str(proj), "--agent", "fake"])
    assert rc == 1
    assert "implement" not in building_agent["roles"]   # build never ran
    assert not (proj / "main.py").exists()


def test_new_requires_dir(tmp_path, building_agent):
    with pytest.raises(SystemExit):       # argparse: -d is required
        main(["new", "idea", "--agent", "fake", "--yes"])


def test_new_requires_idea(tmp_path, building_agent):
    rc = main(["new", "-d", str(tmp_path / "p3"), "--agent", "fake", "--yes"])
    assert rc == 2
