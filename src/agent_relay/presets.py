"""Built-in, zero-config pipelines.

These let a user go from a one-line idea to a built project without authoring
any YAML or prompt files. Prompts are embedded here and written into the target
workspace's work_dir at run time, so the normal file-based hand-off still works.
"""

from __future__ import annotations

from .config import Loop, Pipeline, Step

# --------------------------------------------------------------------------
# Embedded prompts for the "new project" preset.
# {target} = the user's idea; {inputs} = inlined contents of declared inputs.
# --------------------------------------------------------------------------
PLAN_PROMPT = """You are the planning agent. Turn the idea below into a concrete,
reviewable build plan for a brand-new project.

Cover: what to build, the tech stack and project layout (files/dirs), the key
components, and a short test plan. If a prior review is included, REVISE the plan
to address every point it raises.

Output ONLY the plan as markdown.

IDEA:
{target}

PROJECT PLAN AND ANY PRIOR REVIEW:
{inputs}
"""

REVIEW_PROMPT = """You are a senior reviewer. Critically assess the build plan
below for feasibility, missing pieces, risky choices, and gaps in the test plan.
Be specific and actionable.

End your output with EXACTLY ONE of these as the final line:
  VERDICT: APPROVED      — the plan is solid and ready to build
  VERDICT: NEEDS_WORK    — list the changes the planner must make

PLAN TO REVIEW:
{inputs}
"""

BUILD_PROMPT = """You are the implementation agent. Build the project described
in the approved plan below, creating all files in the current working directory.
Add tests and a README. Run the tests if you can.

IMPORTANT: Do NOT commit, push, or create branches. Leave everything in the
working tree. When done, summarize what you created.

APPROVED PLAN:
{inputs}
"""

PRESET_PROMPTS = {
    "plan.md": PLAN_PROMPT,
    "review.md": REVIEW_PROMPT,
    "build.md": BUILD_PROMPT,
}


def new_project_pipeline(
    workspace: str,
    agent: str = "claude",
    build_agent: str | None = None,
    max_iterations: int = 3,
) -> Pipeline:
    """Idea -> plan -> (review loop) -> approve -> build, all in one pipeline.

    The single human gate is BEFORE the build step: you approve the reviewed
    plan, then the project is created in `workspace`.
    """
    build_agent = build_agent or agent
    return Pipeline(
        name="new-project",
        workspace=workspace,
        work_dir=".agent-relay",
        steps=[
            Step(name="plan", agent=agent, role="plan",
                 prompt_file="prompts/plan.md",
                 inputs=[".agent-relay/review.md"],
                 output="PLAN.md"),
            Step(name="review", agent=agent, role="review",
                 prompt_file="prompts/review.md",
                 inputs=["PLAN.md"],
                 output=".agent-relay/review.md"),
            # Approve the reviewed plan BEFORE anything is built.
            Step(name="build", agent=build_agent, role="implement",
                 prompt_file="prompts/build.md",
                 inputs=["PLAN.md"],
                 approve_before=True),
        ],
        loops=[Loop(name="plan-review", steps=["plan", "review"],
                    until_step="review", max_iterations=max_iterations)],
    )
