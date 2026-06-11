"""Adapter for Anthropic's Claude Code CLI (`claude`)."""

from __future__ import annotations

from .base import Agent, AgentContext, register


@register
class ClaudeAgent(Agent):
    name = "claude"
    binary = "claude"

    # Map pipeline roles to Claude permission modes.
    #
    # NB: plan/review are headless TEXT generation — we want the plan/review
    # printed to stdout. We must NOT use --permission-mode plan here: that mode
    # makes Claude call its interactive ExitPlanMode tool, so stdout captures an
    # "approval requested" status message instead of the actual plan. The
    # prompts already instruct "output only markdown / do not modify files", so
    # default mode is correct and safe. Only implement needs edit permissions.
    _ROLE_PERMISSION = {
        "implement": "acceptEdits",
    }

    def build_command(self, ctx: AgentContext) -> list[str]:
        cmd = [self.binary, "-p", ctx.prompt]
        mode = self._ROLE_PERMISSION.get(ctx.role)
        if mode:
            cmd += ["--permission-mode", mode]
        if ctx.model:
            cmd += ["--model", ctx.model]
        cmd += ctx.extra_args
        return cmd
