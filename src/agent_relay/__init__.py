"""agent-relay: chain any AI coding CLIs into an approve-once pipeline."""

from __future__ import annotations

__version__ = "0.1.1"

from .config import Pipeline, Step, load_pipeline
from .runner import Runner, RunResult

__all__ = ["Pipeline", "Step", "load_pipeline", "Runner", "RunResult", "__version__"]
