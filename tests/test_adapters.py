"""Adapter command-building tests — no real CLIs invoked."""

from pathlib import Path

from agent_relay.adapters import get_agent, registered_names
from agent_relay.adapters.base import AgentContext
from agent_relay.adapters.generic import GenericAgent


def ctx(**kw):
    base = dict(prompt="do the thing", workspace=Path("/tmp/ws"), role="implement")
    base.update(kw)
    return AgentContext(**base)


def test_all_builtins_registered():
    for name in ("claude", "codex", "gemini", "aider", "generic"):
        assert name in registered_names()


def test_claude_plan_role_is_plain_text_not_plan_mode():
    # plan/review are headless text generation; --permission-mode plan would
    # trigger the interactive ExitPlanMode tool and corrupt stdout.
    cmd = get_agent("claude").build_command(ctx(role="plan"))
    assert cmd[:2] == ["claude", "-p"]
    assert "--permission-mode" not in cmd


def test_claude_implement_role_accepts_edits():
    cmd = get_agent("claude").build_command(ctx(role="implement"))
    assert "--permission-mode" in cmd and "acceptEdits" in cmd


def test_codex_uses_exec_and_output_file():
    cmd = get_agent("codex").build_command(ctx(output_file=Path("/tmp/o.md")))
    assert cmd[:2] == ["codex", "exec"]
    assert "--skip-git-repo-check" in cmd
    assert "-o" in cmd and "/tmp/o.md" in cmd
    assert cmd[-1] == "do the thing"  # prompt last


def test_generic_substitutes_placeholders():
    agent = get_agent("generic")
    assert isinstance(agent, GenericAgent)
    agent.command_template = ["mytool", "--prompt", "{prompt}", "--out", "{output}"]
    cmd = agent.build_command(ctx(output_file=Path("/tmp/x")))
    assert cmd == ["mytool", "--prompt", "do the thing", "--out", "/tmp/x"]


def test_generic_appends_prompt_when_no_placeholder():
    agent = get_agent("generic")
    agent.command_template = ["mytool", "run"]
    cmd = agent.build_command(ctx())
    assert cmd == ["mytool", "run", "do the thing"]
