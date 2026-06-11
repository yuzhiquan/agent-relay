"""Built-in agent adapters.

Importing this package registers every bundled adapter. Third-party adapters
can register themselves via the ``agent_relay.adapters`` entry-point group or
by importing :func:`agent_relay.adapters.base.register`.
"""

from __future__ import annotations

from importlib import metadata

from .base import Agent, AgentContext, AgentResult, get_agent, register, registered_names

# Import built-ins for their @register side effects.
from . import aider, claude, codex, gemini, generic  # noqa: E402,F401


def load_plugins() -> None:
    """Discover third-party adapters published under our entry-point group."""
    try:
        eps = metadata.entry_points(group="agent_relay.adapters")
    except TypeError:  # pragma: no cover - older importlib API
        eps = metadata.entry_points().get("agent_relay.adapters", [])
    for ep in eps:
        ep.load()  # loading the module triggers its @register decorators


load_plugins()

__all__ = [
    "Agent",
    "AgentContext",
    "AgentResult",
    "get_agent",
    "register",
    "registered_names",
    "load_plugins",
]
