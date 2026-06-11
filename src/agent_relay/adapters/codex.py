"""Adapter for OpenAI's Codex CLI (`codex`)."""

from __future__ import annotations

from .base import Agent, AgentContext, register


@register
class CodexAgent(Agent):
    name = "codex"
    binary = "codex"

    def build_command(self, ctx: AgentContext) -> list[str]:
        # `codex exec` runs non-interactively; --skip-git-repo-check lets it
        # run outside a git repo; -o writes the final message to a file.
        cmd = [self.binary, "exec", "--skip-git-repo-check", "--color", "never"]
        if ctx.model:
            cmd += ["-m", ctx.model]
        if ctx.output_file:
            cmd += ["-o", str(ctx.output_file)]
        cmd += ctx.extra_args
        cmd.append(ctx.prompt)
        return cmd
