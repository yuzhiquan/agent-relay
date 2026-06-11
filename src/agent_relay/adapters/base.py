"""Agent adapter interface and registry.

An *agent* wraps an external coding-assistant CLI (Claude, Codex, Gemini, ...).
Every adapter exposes the same tiny contract so the runner can treat them
interchangeably. Adding support for a new CLI means writing one subclass and
decorating it with ``@register``.
"""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class AgentResult:
    """Outcome of a single agent invocation."""

    ok: bool
    stdout: str = ""
    stderr: str = ""
    output_file: Path | None = None
    returncode: int = 0

    @property
    def message(self) -> str:
        """The agent's final message: file contents if it wrote one, else stdout."""
        if self.output_file and self.output_file.exists():
            return self.output_file.read_text()
        return self.stdout


@dataclass
class AgentContext:
    """Everything an adapter needs to run one step."""

    prompt: str
    workspace: Path
    role: str = "generic"          # plan | review | implement | ...
    output_file: Path | None = None
    model: str | None = None
    extra_args: list[str] = field(default_factory=list)
    # Injectable runner for tests (defaults to subprocess.run).
    runner: Callable[..., subprocess.CompletedProcess] | None = None


class Agent(ABC):
    """Base class for every CLI adapter."""

    #: registry key, e.g. "claude". Set by subclasses.
    name: str = ""
    #: the executable to look for on PATH.
    binary: str = ""

    def __init__(self, binary: str | None = None) -> None:
        if binary:
            self.binary = binary

    def available(self) -> bool:
        """True if the underlying CLI is installed."""
        return shutil.which(self.binary) is not None

    @abstractmethod
    def build_command(self, ctx: AgentContext) -> list[str]:
        """Translate a context into the concrete argv for this CLI."""

    def run(self, ctx: AgentContext) -> AgentResult:
        """Execute the agent. Adapters rarely need to override this."""
        cmd = self.build_command(ctx)
        run = ctx.runner or subprocess.run
        proc = run(
            cmd,
            cwd=str(ctx.workspace),
            capture_output=True,
            text=True,
            check=False,
        )
        return AgentResult(
            ok=proc.returncode == 0,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            output_file=ctx.output_file,
            returncode=proc.returncode,
        )


# --------------------------------------------------------------------------
# Registry — adapters register themselves; third parties can too.
# --------------------------------------------------------------------------
_REGISTRY: dict[str, type[Agent]] = {}


def register(cls: type[Agent]) -> type[Agent]:
    """Class decorator: add an adapter to the registry under its ``name``."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must set a non-empty `name`")
    _REGISTRY[cls.name] = cls
    return cls


def get_agent(name: str, binary: str | None = None) -> Agent:
    """Instantiate a registered adapter by name."""
    try:
        cls = _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown agent '{name}'. Registered: {known}") from None
    return cls(binary=binary)


def registered_names() -> list[str]:
    return sorted(_REGISTRY)
