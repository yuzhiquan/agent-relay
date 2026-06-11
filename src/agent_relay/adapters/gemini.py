"""Adapter for Google's Gemini CLI (`gemini`)."""

from __future__ import annotations

from .base import Agent, AgentContext, register


@register
class GeminiAgent(Agent):
    name = "gemini"
    binary = "gemini"

    def build_command(self, ctx: AgentContext) -> list[str]:
        # `gemini -p` runs a one-shot non-interactive prompt.
        cmd = [self.binary, "-p", ctx.prompt]
        if ctx.model:
            cmd += ["-m", ctx.model]
        cmd += ctx.extra_args
        return cmd
