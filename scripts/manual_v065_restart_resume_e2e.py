from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.models import AgentKind
from ai_lab_os.multi_agent_runtime import MultiAgentRuntimeConfig, build_core_router
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.skill_selector import route_skill_request
from ai_lab_os.supervisor_loop import SupervisorPolicy, resume_supervisor_from_store, run_supervisor_loop
from ai_lab_os.task_planner import PlannedTaskKind


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


def check_url(url: str, *, timeout_seconds: int = 3) -> None:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response.read(1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Backend unavailable: {url}: {exc}") from exc


def graduation_skill() -> SkillContract:
    return SkillContract(
        skill_id="restart-resume-research-code-verify",
        name="Restart Resume Research Code Verify",
        description="Research a topic, verify local code, then verify the safe computer runtime across a restart.",
        inputs=(SkillInputSpec("topic", "Technical topic to research and verify."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        permissions=("web.search", "coding.verify", "computer.mock"),
        success_criteria=("The resumed execution reaches GOAL_COMPLETE without repeating completed work.",),
        metadata={"triggers": "research,研究,restart,重启,resume,恢复,pytest"},
        steps=(
            SkillStepSpec(
                step_id="research",
                kind=PlannedTaskKind.ANALYZE,
                agent=AgentKind.RESEARCH,
                description_template="Research {topic} and return evidence.",
                success_criteria=("At least one research source is returned.",),
                metadata_templates={"query": "{topic}"},
            ),
            SkillStepSpec(
                step_id="coding",
                kind=PlannedTaskKind.VERIFY,
                agent=AgentKind.CODING,
                description_template="Verify the local AI Lab OS regression for {topic}.",
                depends_on=("research",),
                success_criteria=("Configured pytest command passes.",),
            ),
            SkillStepSpec(
                step_id="computer",
                kind=PlannedTaskKind.VERIFY,
                agent=AgentKind.COMPUTER,
                description_template="Verify the safe computer runtime after resuming {topic}.",
                depends_on=("coding",),
                success_criteria=("Brain accepts and completes the mock Windows action.",),
                metadata_templates={
                    "action": "click",
                    "args_json": "{}",
                    "window_title": "Notepad",
                    "expected_process": "notepad.exe",
                },
            ),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="V0.6.5 real restart + resume graduation E2E")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--brain-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--searxng-base-url", default="http://127.0.0.1:8888")
    parser.add_argument(
        "--request",
        default="请研究 pytest fixture，并验证代码和电脑执行链可以在重启后继续完成",
    )
    args = parser.parse_args()

    repository = Path(args.repo).resolve()
    branch = current_branch(repository)
    print("=" * 78)
    print("V0.6.5 REAL RESTART + RESUME E2E")
    print("=" * 78)
    print(f"REQUEST  = {args.request}")
    print(f"REPO     = {repository}")
    print(f"BRANCH   = {branch}")
    print(f"BRAIN    = {args.brain_base_url}")
    print(f"SEARXNG  = {args.searxng_base_url}")
    print("SAFETY   = Computer real actions disabled (approved=false, dry_run=true)")
    print()

    try:
        check_url(args.brain_base_url.rstrip("/") + "/openapi.json")
        check_url(args.searxng_base_url.rstrip("/") + "/search?q=pytest&format=json")
    except RuntimeError as exc:
        print("RESULT   = BACKEND_OFFLINE")
        print(f"ERROR    = {exc}")
        return 2

    registry = SkillRegistry.from_skills((graduation_skill(),))
    routed = route_skill_request(args.request, registry, goal_id="v065-restart-resume-e2e")
    plan = routed.compiled.plan
    first_task_id = plan.tasks[0].task_id

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
    router = build_core_router(config)

    with tempfile.TemporaryDirectory(prefix="ai-lab-v065-") as temporary:
        state_path = Path(temporary) / "goals.json"
        history_path = Path(temporary) / "history.jsonl"
        store_phase_1 = JsonGoalStore(state_path)
        history_phase_1 = JsonExecutionHistory(history_path)

        print(f"SKILL    = {routed.selection.skill.skill_id}")
        print(f"TASKS    = {len(plan.tasks)}")
        print("PHASE 1  = Run exactly one cycle, persist Task 1, then simulate process stop")

        phase_1 = run_supervisor_loop(
            plan,
            router.execute,
            policy=SupervisorPolicy(max_cycles=1),
            goal_store=store_phase_1,
            history_store=history_phase_1,
        )
        saved = store_phase_1.load(plan.goal_id)
        print(f"PHASE1_STATUS = {phase_1.status}")
        print(f"PERSISTED     = {saved.status}")
        print(f"RESUME_CURSOR = {saved.resume_cursor}")
        print(f"COMPLETED     = {', '.join(task.task_id for task in saved.tasks if task.status == 'complete')}")

        if saved.tasks[0].status != "complete":
            print("RESULT   = FAILED")
            print("ERROR    = Phase 1 did not persist the first task as complete.")
            return 1

        print()
        print("PHASE 2  = New store/runtime objects simulate restart; resume unfinished work")
        store_phase_2 = JsonGoalStore(state_path)
        history_phase_2 = JsonExecutionHistory(history_path)
        router_after_restart = build_core_router(config)
        phase_2 = resume_supervisor_from_store(
            plan.goal_id,
            router_after_restart.execute,
            store_phase_2,
            policy=SupervisorPolicy(max_cycles=50),
            history_store=history_phase_2,
        )
        final_state = store_phase_2.load(plan.goal_id)
        final_history = history_phase_2.latest(goal_id=plan.goal_id)

        running_first = [
            event for event in phase_2.events
            if event.startswith(f"RUNNING:{first_task_id}:")
        ]
        print(f"STATUS        = {phase_2.status}")
        print(f"CYCLES        = {phase_2.cycles}")
        print(f"FINAL_CURSOR  = {final_state.resume_cursor}")
        print(f"HISTORY       = {final_history.status}, attempts={final_history.total_attempts}")
        print("EVENTS:")
        for event in phase_2.events:
            print(f"  {event}")

        if running_first:
            print("RESULT   = FAILED")
            print("ERROR    = Completed Task 1 was executed again after restart.")
            return 1
        if phase_2.status != "complete" or "GOAL_COMPLETE" not in phase_2.events:
            print("RESULT   = FAILED")
            print("ERROR    = Resumed execution did not reach GOAL_COMPLETE.")
            return 1
        if final_state.resume_cursor is not None:
            print("RESULT   = FAILED")
            print("ERROR    = Final persistent state still has a resume cursor.")
            return 1
        if final_history.status != "complete":
            print("RESULT   = FAILED")
            print("ERROR    = Final execution history is not complete.")
            return 1

    print("RESULT   = DONE")
    print("MESSAGE  = V0.6.5 restart + resume E2E reached GOAL_COMPLETE without repeating completed work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
