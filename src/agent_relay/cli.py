"""Command-line interface for agent-relay."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .adapters import registered_names
from .config import load_pipeline
from .presets import PRESET_PROMPTS, new_project_pipeline
from .runner import RunResult, Runner


def _auto_approve(step_name: str, result: RunResult) -> bool:
    """Non-interactive gate used by --yes / CI: always approve."""
    return True


def _approval_gate(step_name: str, result: RunResult) -> bool:
    """Default human gate: show what changed, ask to continue."""
    print(f"\n\033[1;35m━━ Approval gate after '{step_name}' ━━\033[0m")

    # Show a git diff if we're in a repo; otherwise show the agent's message.
    try:
        diff = subprocess.run(
            ["git", "diff", "--stat"], capture_output=True, text=True, check=False
        )
        if diff.returncode == 0 and diff.stdout.strip():
            print("Changed files:\n" + diff.stdout)
    except FileNotFoundError:
        pass
    if result.last_message:
        print("Agent message (truncated):")
        print("    " + result.last_message.strip()[:1500].replace("\n", "\n    "))

    try:
        ans = input("\nApprove and continue? [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def cmd_run(args: argparse.Namespace) -> int:
    pipeline = load_pipeline(args.pipeline)
    if args.workspace:
        pipeline.workspace = args.workspace
    if args.max_iterations is not None:
        if args.max_iterations < 1:
            print("error: --max-iterations must be >= 1", file=sys.stderr)
            return 2
        # Override every loop's cap for this run.
        for lp in pipeline.loops:
            lp.max_iterations = args.max_iterations

    target = args.target
    if args.target_file:
        target = Path(args.target_file).read_text()
    if target is None and not args.resume:
        # Not fatal: some pipelines bake the goal into their prompt files.
        # Only the {target} placeholder would be left empty.
        print("note: no target given; prompts using {target} will see an empty value",
              file=sys.stderr)

    runner = Runner(
        pipeline,
        target=target or "",
        approval_fn=_auto_approve if args.yes else _approval_gate,
        dry_run=args.dry_run,
    )
    result = runner.run(resume=args.resume)
    return 1 if result.aborted else 0


def cmd_new(args: argparse.Namespace) -> int:
    """Zero-config: idea -> plan -> review loop -> approve -> build a project."""
    idea = args.idea
    if args.idea_file:
        idea = Path(args.idea_file).read_text()
    if not idea:
        print("error: provide an idea (positional or --idea-file)", file=sys.stderr)
        return 2

    workspace = Path(args.dir).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    # Write the embedded preset prompts into the workspace's work_dir so the
    # normal prompt_file hand-off works — no config from the user required.
    prompts_dir = workspace / ".agent-relay" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for fname, text in PRESET_PROMPTS.items():
        (prompts_dir / fname).write_text(text)

    pipeline = new_project_pipeline(
        workspace=str(workspace),
        agent=args.agent,
        build_agent=args.build_agent,
        max_iterations=args.max_iterations or 3,
    )
    # prompt_file paths ("prompts/plan.md") resolve against base_dir.
    pipeline.base_dir = str(workspace / ".agent-relay")

    print(f"💡 idea → project in {workspace}")
    print(f"   plan+review: {args.agent}   build: {args.build_agent or args.agent}   "
          f"max loops: {args.max_iterations or 3}")

    runner = Runner(
        pipeline,
        target=idea,
        approval_fn=_auto_approve if args.yes else _plan_approval_gate,
        dry_run=args.dry_run,
    )
    result = runner.run(resume=args.resume)
    if result.aborted:
        return 1
    print(f"\n✅ Project created in {workspace}")
    return 0


def _plan_approval_gate(step_name: str, result: RunResult) -> bool:
    """Gate shown before the build step: print the reviewed plan, ask to build."""
    print(f"\n\033[1;35m━━ Final plan ready — approve before building ({step_name}) ━━\033[0m")
    plan = Path("PLAN.md")
    # The gate runs with cwd at the workspace via the runner; fall back to message.
    if result.state and result.state.completed:
        for rec in result.state.completed:
            if rec.output_file and rec.output_file.endswith("PLAN.md"):
                plan = Path(rec.output_file)
    if plan.exists():
        print("\n" + plan.read_text())
    elif result.last_message:
        print(result.last_message)

    try:
        ans = input("\nBuild this project? [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def cmd_agents(_: argparse.Namespace) -> int:
    print("Registered agents:")
    for name in registered_names():
        print(f"  - {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-relay",
        description="Chain any AI coding CLIs into an approve-once pipeline.",
    )
    p.add_argument("--version", action="version", version=f"agent-relay {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run a pipeline")
    r.add_argument("target", nargs="?", help="the target/goal description")
    r.add_argument("-p", "--pipeline", default="pipeline.yaml", help="pipeline YAML file")
    r.add_argument("-f", "--target-file", help="read the target from a file")
    r.add_argument("-w", "--workspace", help="override the workspace dir")
    r.add_argument("--resume", action="store_true", help="resume from saved state")
    r.add_argument("--dry-run", action="store_true", help="print commands, run nothing")
    r.add_argument("--yes", action="store_true", help="auto-approve all gates (CI)")
    r.add_argument("--max-iterations", type=int, metavar="N",
                   help="override the iteration cap for all loops")
    r.set_defaults(func=cmd_run)

    n = sub.add_parser(
        "new",
        help="zero-config: turn an idea into a reviewed plan, then build a project",
    )
    n.add_argument("idea", nargs="?", help="one-line description of what to build")
    n.add_argument("-d", "--dir", required=True, metavar="DIR",
                   help="folder to create the project in")
    n.add_argument("-f", "--idea-file", help="read the idea from a file")
    n.add_argument("--agent", default="claude",
                   help="agent for plan+review (default: claude)")
    n.add_argument("--build-agent", help="agent for the build step (default: --agent)")
    n.add_argument("--max-iterations", type=int, metavar="N",
                   help="plan↔review loop cap (default: 3)")
    n.add_argument("--resume", action="store_true", help="resume from saved state")
    n.add_argument("--dry-run", action="store_true", help="print commands, run nothing")
    n.add_argument("--yes", action="store_true", help="auto-approve the plan (CI)")
    n.set_defaults(func=cmd_new)

    a = sub.add_parser("agents", help="list registered agent adapters")
    a.set_defaults(func=cmd_agents)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
