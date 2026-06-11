"""A config-driven adapter for ANY CLI — no Python required.

Define the command as a template in your pipeline.yaml and the generic adapter
fills in placeholders. This is the zero-code path to supporting a new agent::

    - name: implement
      agent: generic
      command: ["mytool", "run", "--prompt", "{prompt}", "--out", "{output}"]

Supported placeholders: {prompt} {output} {workspace} {model} {role}
A bare "{prompt}" token is replaced in-place; if the template contains no
{prompt}, the prompt is appended as the final argument.
"""

from __future__ import annotations

from .base import Agent, AgentContext, register


@register
class GenericAgent(Agent):
    name = "generic"
    binary = ""  # resolved from the template's argv[0]

    def __init__(self, binary: str | None = None) -> None:
        super().__init__(binary)
        # Set by the runner from the step's `command:` list.
        self.command_template: list[str] = []

    def available(self) -> bool:
        # Availability is checked lazily when the command is known.
        return True

    def build_command(self, ctx: AgentContext) -> list[str]:
        if not self.command_template:
            raise ValueError(
                "generic agent requires a `command:` list in the pipeline step"
            )
        subs = {
            "prompt": ctx.prompt,
            "output": str(ctx.output_file) if ctx.output_file else "",
            "workspace": str(ctx.workspace),
            "model": ctx.model or "",
            "role": ctx.role,
        }
        cmd: list[str] = []
        prompt_seen = False
        for tok in self.command_template:
            if tok == "{prompt}":
                prompt_seen = True
            try:
                cmd.append(tok.format(**subs))
            except (KeyError, IndexError):
                cmd.append(tok)  # leave unknown placeholders untouched
        if not prompt_seen:
            cmd.append(ctx.prompt)
        return cmd
