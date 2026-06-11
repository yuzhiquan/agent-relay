"""Adapter for Aider (`aider`), a git-native pair-programming CLI."""

from __future__ import annotations

from .base import Agent, AgentContext, register


@register
class AiderAgent(Agent):
    name = "aider"
    binary = "aider"

    def build_command(self, ctx: AgentContext) -> list[str]:
        # --message runs one instruction non-interactively then exits.
        # --yes auto-confirms; we forbid commits so the human gate stays in control.
        cmd = [self.binary, "--message", ctx.prompt, "--yes", "--no-auto-commits"]
        if ctx.model:
            cmd += ["--model", ctx.model]
        cmd += ctx.extra_args
        return cmd
