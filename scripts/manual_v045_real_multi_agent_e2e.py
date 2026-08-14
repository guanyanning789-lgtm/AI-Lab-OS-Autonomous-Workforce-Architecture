from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.models import AgentKind
from ai_lab_os.multi_agent_runtime import MultiAgentRuntimeConfig, run_multi_agent_plan
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract


def current_branch(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(repository),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    branch = (completed.stdout or "").strip()
    if completed.returncode != 0 or not branch:
        raise RuntimeError("Cannot determine current git branch")
    return branch


def build_plan() -> TaskPlanContract:
    goal_id = "v045-real-multi-agent-e2e"
    research_id = f"{goal_id}-research"
    coding_id = f"{goal_id}-coding"
    computer_id = f"{goal_id}-computer"
    return TaskPlanContract(
        goal_id=goal_id,
        planner_version="v0.4.5-local-e2e",
        tasks=(
            PlannedTask(
                task_id=research_id,
                goal_id=goal_id,
                sequence=1,
                kind=PlannedTaskKind.ANALYZE,
                description="Research Python pytest official information for a safe local verification run.",
                agent=AgentKind.RESEARCH,
                success_criteria=("At least one research source is returned.",),
                metadata={"query": "pytest Python testing framework"},
            ),
            PlannedTask(
                task_id=coding_id,
                goal_id=goal_id,
                sequence=2,
                kind=PlannedTaskKind.IMPLEMENT,
                description="Verify the AI Lab OS agent router regression tests without modifying source files.",
                agent=AgentKind.CODING,
                success_criteria=("Configured pytest command passes.",),
                depends_on=(research_id,),
            ),
            PlannedTask(
                task_id=computer_id,
                goal_id=goal_id,
                sequence=3,
                kind=PlannedTaskKind.VERIFY,
                description="Send one Brain-supported Windows click action through the Computer executor in mock mode.",
                agent=AgentKind.COMPUTER,
                success_criteria=("Brain accepts and completes the mock Windows action.",),
                depends_on=(coding_id,),
                metadata={
                    "action": "click",
                    "args_json": "{}",
                    "window_title": "Notepad",
                    "expected_process": "notepad.exe",
                },
            ),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="V0.4.5 real local multi-agent graduation E2E")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--brain-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--searxng-base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    repository = Path(args.repo).resolve()
    branch = current_branch(repository)
    print("=" * 78)
    print("V0.4.5 REAL MULTI-AGENT E2E")
    print("=" * 78)
    print(f"REPO     = {repository}")
    print(f"BRANCH   = {branch}")
    print(f"BRAIN    = {args.brain_base_url}")
    print(f"SEARXNG  = {args.searxng_base_url}")
    print("SAFETY   = Computer real actions disabled (approved=false, dry_run=true)")
    print()

    config = MultiAgentRuntimeConfig(
        repository_path=str(repository),
        branch=branch,
        tests=("python -m pytest tests/test_agent_router_v035.py -q",),
        allowed_files=(),
        brain_base_url=args.brain_base_url,
        searxng_base_url=args.searxng_base_url,
        allow_cline_repair=False,
        computer_approved=False,
        computer_dry_run=True,
    )

    result = run_multi_agent_plan(build_plan(), config)
    print(f"STATUS   = {result.status}")
    print(f"CYCLES   = {result.cycles}")
    print(f"COMPLETE = {', '.join(result.completed_tasks)}")
    if result.failed_task_id:
        print(f"FAILED   = {result.failed_task_id}")
    print(f"MESSAGE  = {result.message}")
    print("EVENTS:")
    for event in result.events:
        print(f"  {event}")

    if result.status == "complete" and "GOAL_COMPLETE" in result.events:
        print("RESULT   = DONE")
        print("MESSAGE  = V0.4.5 real local multi-agent E2E reached GOAL_COMPLETE.")
        return 0

    print("RESULT   = FAILED")
    print("ERROR    = Multi-agent graduation E2E did not reach GOAL_COMPLETE.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
