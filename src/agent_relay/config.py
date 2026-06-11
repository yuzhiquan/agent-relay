"""Pipeline configuration model and loader.

A pipeline is plain data (YAML), so adding a step or swapping an agent never
requires touching Python. This module parses and validates that data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class Step:
    name: str
    agent: str
    role: str = "generic"
    prompt: str | None = None             # inline prompt template
    prompt_file: str | None = None        # path to a prompt template
    inputs: list[str] = field(default_factory=list)   # files fed to the prompt
    output: str | None = None             # file the agent writes
    model: str | None = None
    command: list[str] | None = None      # for the `generic` agent
    extra_args: list[str] = field(default_factory=list)
    approve_before: bool = False          # human gate BEFORE this step runs
    approve_after: bool = False           # human gate AFTER this step


@dataclass
class Loop:
    """Repeat a contiguous group of steps until a verdict approves, or a cap.

    The verdict step (default: the loop's last step) is expected to end its
    output with ``approved_marker``. Each iteration re-runs the group; the
    feedback path is the normal file hand-off (have the first step list the
    verdict step's output as an input, so the next pass sees the last review).
    """

    name: str
    steps: list[str]                     # step names in this loop, in order
    max_iterations: int = 3
    until_step: str | None = None        # step whose output holds the verdict
    approved_marker: str = "VERDICT: APPROVED"


@dataclass
class Pipeline:
    name: str
    steps: list[Step]
    loops: list[Loop] = field(default_factory=list)
    workspace: str = "."
    work_dir: str = ".agent-relay"
    # Directory of the pipeline YAML; prompt_file paths resolve against it.
    base_dir: str = "."

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Pipeline":
        raw_steps = data.get("steps") or []
        if not raw_steps:
            raise ValueError("pipeline has no steps")
        steps = []
        for i, s in enumerate(raw_steps):
            if "name" not in s or "agent" not in s:
                raise ValueError(f"step {i} must have `name` and `agent`")
            steps.append(
                Step(
                    name=s["name"],
                    agent=s["agent"],
                    role=s.get("role", "generic"),
                    prompt=s.get("prompt"),
                    prompt_file=s.get("prompt_file"),
                    inputs=s.get("inputs", []),
                    output=s.get("output"),
                    model=s.get("model"),
                    command=s.get("command"),
                    extra_args=s.get("extra_args", []),
                    approve_before=bool(s.get("approve_before", False)),
                    approve_after=bool(s.get("approve_after", False)),
                )
            )

        step_names = [s.name for s in steps]
        loops = []
        for j, lp in enumerate(data.get("loops") or []):
            if "name" not in lp or not lp.get("steps"):
                raise ValueError(f"loop {j} must have `name` and non-empty `steps`")
            loop_steps = lp["steps"]
            # All referenced steps must exist and form a contiguous block.
            try:
                idxs = [step_names.index(n) for n in loop_steps]
            except ValueError as e:
                raise ValueError(f"loop '{lp['name']}' references unknown step: {e}") from None
            if idxs != list(range(idxs[0], idxs[0] + len(idxs))):
                raise ValueError(
                    f"loop '{lp['name']}' steps must be contiguous and in pipeline order"
                )
            until = lp.get("until_step")
            if until and until not in loop_steps:
                raise ValueError(f"loop '{lp['name']}' until_step '{until}' not in its steps")
            loops.append(
                Loop(
                    name=lp["name"],
                    steps=loop_steps,
                    max_iterations=int(lp.get("max_iterations", 3)),
                    until_step=until,
                    approved_marker=lp.get("approved_marker", "VERDICT: APPROVED"),
                )
            )

        return cls(
            name=data.get("name", "pipeline"),
            steps=steps,
            loops=loops,
            workspace=data.get("workspace", "."),
            work_dir=data.get("work_dir", ".agent-relay"),
        )


def load_pipeline(path: str | Path) -> Pipeline:
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    path = Path(path)
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    pipeline = Pipeline.from_dict(data)
    pipeline.base_dir = str(path.resolve().parent)
    return pipeline
