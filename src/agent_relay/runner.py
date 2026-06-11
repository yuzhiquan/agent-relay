"""The pipeline engine.

Runs each step in order, feeding files between agents (the hand-off medium),
honouring human-approval gates, and persisting a run journal so a crashed or
interrupted run can resume where it left off.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .adapters import AgentContext, AgentResult, get_agent
from .adapters.generic import GenericAgent
from .config import Loop, Pipeline, Step


@dataclass
class StepRecord:
    name: str
    ok: bool
    returncode: int
    output_file: str | None = None


@dataclass
class RunState:
    """Journal persisted to <work_dir>/state.json for resume."""

    pipeline: str
    target: str
    completed: list[StepRecord] = field(default_factory=list)

    def done_steps(self) -> set[str]:
        return {r.name for r in self.completed}


# A prompt for the human at an approval gate. Returns True to continue.
ApprovalFn = Callable[[str, "RunResult"], bool]


@dataclass
class RunResult:
    state: RunState
    aborted: bool = False
    last_message: str = ""


def _render_prompt(step: Step, target: str, workspace: Path, base_dir: Path) -> str:
    """Build the step's prompt from its template, target, and input files.

    ``prompt_file`` resolves against the pipeline file's directory (base_dir);
    ``inputs`` resolve against the workspace (they are produced during the run).
    """
    if step.prompt_file:
        template = (base_dir / step.prompt_file).read_text()
    elif step.prompt:
        template = step.prompt
    else:
        template = "{target}"

    # Inline the contents of declared input files so the agent sees them even
    # if it has no filesystem awareness. Files on disk remain the source of truth.
    input_blocks = []
    for rel in step.inputs:
        p = workspace / rel
        if p.exists():
            input_blocks.append(f"\n\n--- {rel} ---\n{p.read_text()}")
    inputs_text = "".join(input_blocks)

    return template.replace("{target}", target).replace("{inputs}", inputs_text) + (
        inputs_text if "{inputs}" not in template else ""
    )


class Runner:
    def __init__(
        self,
        pipeline: Pipeline,
        target: str,
        approval_fn: ApprovalFn | None = None,
        dry_run: bool = False,
        log: Callable[[str], None] = print,
    ) -> None:
        self.pipeline = pipeline
        self.target = target
        self.workspace = Path(pipeline.workspace).resolve()
        self.base_dir = Path(pipeline.base_dir).resolve()
        self.work_dir = self.workspace / pipeline.work_dir
        self.approval_fn = approval_fn
        self.dry_run = dry_run
        self.log = log

    # -- state persistence --------------------------------------------------
    def _state_path(self) -> Path:
        return self.work_dir / "state.json"

    def _load_state(self) -> RunState:
        p = self._state_path()
        if p.exists():
            raw = json.loads(p.read_text())
            recs = [StepRecord(**r) for r in raw.get("completed", [])]
            return RunState(raw["pipeline"], raw["target"], recs)
        return RunState(self.pipeline.name, self.target)

    def _save_state(self, state: RunState) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._state_path().write_text(
            json.dumps(
                {
                    "pipeline": state.pipeline,
                    "target": state.target,
                    "completed": [asdict(r) for r in state.completed],
                },
                indent=2,
            )
        )

    # -- single-step execution ---------------------------------------------
    def _execute_step(self, step: Step) -> AgentResult:
        """Run one step's agent and persist its output file. No state/gates."""
        prompt = _render_prompt(step, self.target, self.workspace, self.base_dir)
        out_file = (self.workspace / step.output) if step.output else None

        agent = get_agent(step.agent)
        if isinstance(agent, GenericAgent) and step.command:
            agent.command_template = step.command

        if self.dry_run:
            ctx = AgentContext(
                prompt=prompt, workspace=self.workspace, role=step.role,
                output_file=out_file, model=step.model, extra_args=step.extra_args,
            )
            self.log("   DRY-RUN cmd: " + " ".join(agent.build_command(ctx)))
            return AgentResult(ok=True, output_file=out_file)

        if not agent.available():
            self.log(f"✖  agent '{step.agent}' CLI not found on PATH")
            return AgentResult(ok=False, returncode=127)

        ctx = AgentContext(
            prompt=prompt, workspace=self.workspace, role=step.role,
            output_file=out_file, model=step.model, extra_args=step.extra_args,
        )
        res = agent.run(ctx)
        if out_file and not out_file.exists() and res.stdout:
            # Agent wrote to stdout instead of the file; capture it.
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(res.stdout)
        return res

    # -- execution ----------------------------------------------------------
    def run(self, resume: bool = False) -> RunResult:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        state = self._load_state() if resume else RunState(self.pipeline.name, self.target)
        done = state.done_steps()
        result = RunResult(state=state)

        # Map the first step of each loop to its Loop, and collect every step
        # that belongs to a loop (so the main walk knows to delegate/skip).
        loop_by_first = {lp.steps[0]: lp for lp in self.pipeline.loops}
        in_loop = {name for lp in self.pipeline.loops for name in lp.steps}
        steps_by_name = {s.name: s for s in self.pipeline.steps}

        for step in self.pipeline.steps:
            # A loop is driven from its first step; other member steps are
            # handled inside _run_loop, so skip them in the main walk.
            if step.name in loop_by_first:
                if not self._run_loop(loop_by_first[step.name], steps_by_name,
                                      state, done, result):
                    return result
                continue
            if step.name in in_loop:
                continue

            if not self._run_one(step, state, done, result):
                return result

        return result

    def _run_one(self, step: Step, state: RunState, done: set,
                 result: RunResult) -> bool:
        """Run a non-loop step, record state, apply its gate. False => stop."""
        if step.name in done:
            self.log(f"⏭  skip (already done): {step.name}")
            return True

        # Gate BEFORE running — e.g. approve the reviewed plan before building.
        if step.approve_before and not self.dry_run:
            if self.approval_fn is None or not self.approval_fn(f"before:{step.name}", result):
                self.log("⏸  not approved — stopping.")
                result.aborted = True
                return False

        self.log(f"▶  {step.name}  [{step.agent}/{step.role}]")
        res = self._execute_step(step)
        result.last_message = res.message

        if self.dry_run:
            return True

        state.completed.append(
            StepRecord(step.name, res.ok, res.returncode,
                       str(self.workspace / step.output) if step.output else None)
        )
        self._save_state(state)

        if not res.ok:
            self.log(f"✖  step '{step.name}' failed (rc={res.returncode})")
            self.log(res.stderr.strip()[:2000])
            result.aborted = True
            return False

        self.log(f"✔  {step.name} done")

        if step.approve_after:
            if self.approval_fn is None or not self.approval_fn(step.name, result):
                self.log("⏸  not approved — stopping.")
                result.aborted = True
                return False
        return True

    def _run_loop(self, loop: Loop, steps_by_name: dict, state: RunState,
                  done: set, result: RunResult) -> bool:
        """Iterate a loop's steps until the verdict approves or the cap is hit."""
        verdict_step = loop.until_step or loop.steps[-1]
        loop_steps = [steps_by_name[n] for n in loop.steps]

        for iteration in range(1, loop.max_iterations + 1):
            self.log(f"🔁 loop '{loop.name}' — iteration {iteration}/{loop.max_iterations}")
            verdict_text = ""
            for step in loop_steps:
                self.log(f"▶  {step.name}  [{step.agent}/{step.role}]")
                res = self._execute_step(step)
                result.last_message = res.message
                if step.name == verdict_step:
                    verdict_text = res.message

                if self.dry_run:
                    continue

                # Loop steps re-run each iteration, so record them uniquely.
                state.completed.append(
                    StepRecord(f"{step.name}#{iteration}", res.ok, res.returncode,
                               str(self.workspace / step.output) if step.output else None)
                )
                self._save_state(state)

                if not res.ok:
                    self.log(f"✖  step '{step.name}' failed (rc={res.returncode})")
                    self.log(res.stderr.strip()[:2000])
                    result.aborted = True
                    return False
                self.log(f"✔  {step.name} done")

            if self.dry_run:
                self.log(f"   (dry-run: would check for '{loop.approved_marker}')")
                break

            if loop.approved_marker in verdict_text:
                self.log(f"✅ loop '{loop.name}' approved on iteration {iteration}")
                break
            if iteration == loop.max_iterations:
                self.log(f"🛑 loop '{loop.name}' hit max_iterations "
                         f"({loop.max_iterations}) without approval — continuing anyway")
            else:
                self.log(f"↩  not approved; re-running loop '{loop.name}'")
        return True
