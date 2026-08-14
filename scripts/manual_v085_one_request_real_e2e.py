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
from ai_lab_os.goal_intake import GoalIntakeRequest
from ai_lab_os.models import AgentKind
from ai_lab_os.multi_agent_runtime import MultiAgentRuntimeConfig, build_core_router
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.recovery_handoff import launch_with_recovery_handoff
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy
from ai_lab_os.task_planner import PlannedTaskKind


def current_branch(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(repository),
        capture_output=True,
        text=True,
        check=False,
    )
    branch = (completed.stdout or "").strip()
    if completed.returncode != 0 or not branch:
        raise RuntimeError("Cannot determine current git branch")
    return branch


def check_url(url: str, timeout: int = 3) -> None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as response:
            response.read(1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Backend unavailable: {url}: {exc}") from exc


def graduation_skill() -> SkillContract:
    return SkillContract(
        skill_id="one-request-research-code-computer",
        name="One Request Research Code Computer",
        description="Research a technical topic, verify local code, then verify the safe computer runtime from one request.",
        inputs=(SkillInputSpec("topic", "Technical topic to research and verify."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        permissions=("web.search", "coding.verify", "computer.mock"),
        success_criteria=("One natural-language request reaches GOAL_COMPLETE with durable recovery available.",),
        metadata={"triggers": "research,研究,pytest,验证,電腦,电脑"},
        steps=(
            SkillStepSpec(
                "research",
                PlannedTaskKind.ANALYZE,
                AgentKind.RESEARCH,
                "Research {topic} and return evidence.",
                metadata_templates={"query": "{topic}"},
            ),
            SkillStepSpec(
                "coding",
                PlannedTaskKind.VERIFY,
                AgentKind.CODING,
                "Verify the local AI Lab regression path for {topic}.",
                depends_on=("research",),
            ),
            SkillStepSpec(
                "computer",
                PlannedTaskKind.VERIFY,
                AgentKind.COMPUTER,
                "Verify the safe computer runtime for {topic}.",
                depends_on=("coding",),
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
    parser = argparse.ArgumentParser(description="V0.8.5 one-request real graduation E2E")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--brain-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--searxng-base-url", default="http://127.0.0.1:8888")
    parser.add_argument(
        "--request",
        default="请研究 pytest fixture，并验证本地代码和电脑执行链是否正常",
    )
    args = parser.parse_args()

    repository = Path(args.repo).resolve()
    branch = current_branch(repository)
    print("=" * 78)
    print("V0.8.5 ONE-REQUEST REAL E2E")
    print("=" * 78)
    print(f"REQUEST  = {args.request}")
    print(f"REPO     = {repository}")
    print(f"BRANCH   = {branch}")
    print(f"BRAIN    = {args.brain_base_url}")
    print(f"SEARXNG  = {args.searxng_base_url}")
    print("SAFETY   = Computer real actions disabled (approved=false, dry_run=true)")
    print("ENTRY    = One GoalIntakeRequest only; no manual Goal/TaskPlan/Resume plumbing")
    print()

    try:
        check_url(args.brain_base_url.rstrip("/") + "/openapi.json")
        check_url(args.searxng_base_url.rstrip("/") + "/search?q=pytest&format=json")
    except RuntimeError as exc:
        print("RESULT   = BACKEND_OFFLINE")
        print(f"ERROR    = {exc}")
        return 2

    registry = SkillRegistry.from_skills((graduation_skill(),))
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

    with tempfile.TemporaryDirectory(prefix="ai-lab-v085-") as temporary:
        store = JsonGoalStore(Path(temporary) / "goals.json")
        history = JsonExecutionHistory(Path(temporary) / "history.jsonl")

        # Deliberately permit only one initial cycle. The same single API call must
        # hand the durable unfinished goal to recovery and finish the remaining work.
        result = launch_with_recovery_handoff(
            GoalIntakeRequest(args.request, goal_id="v085-one-request-real-e2e"),
            registry,
            router.execute,
            store,
            launch_policy=SupervisorPolicy(max_cycles=1),
            recovery_policy=SupervisorPolicy(max_cycles=50),
            history_store=history,
        )
        final = store.load(result.goal_id)

        print(f"GOAL_ID        = {result.goal_id}")
        print(f"SKILL          = {result.launch.routed.skill_id}")
        print(f"LAUNCH_STATUS  = {result.launch.supervisor.status}")
        print(f"HANDED_OFF     = {result.handed_off}")
        print(f"FINAL_STATUS   = {result.final_status}")
        print(f"FINAL_CURSOR   = {final.resume_cursor}")
        print("LAUNCH_EVENTS:")
        for event in result.launch.supervisor.events:
            print(f"  {event}")

        recovery_result = None
        if result.recovery is not None:
            recovery_result = next(
                (item for item in result.recovery.results if item.goal_id == result.goal_id),
                None,
            )
            print(f"RECOVERY_SCAN  = {result.recovery.scan_number}")
            if recovery_result is not None:
                print(f"DECISION       = {recovery_result.decision.action.value}")
                if recovery_result.supervisor_result is not None:
                    print("RECOVERY_EVENTS:")
                    for event in recovery_result.supervisor_result.events:
                        print(f"  {event}")

        if result.launch.supervisor.status != "cycle_limit":
            print("RESULT   = FAILED")
            print("ERROR    = Graduation test did not exercise Recovery Handoff.")
            return 1
        if not result.handed_off or recovery_result is None:
            print("RESULT   = FAILED")
            print("ERROR    = Unfinished launch was not handed to recovery.")
            return 1
        if final.status != "complete" or final.resume_cursor is not None:
            print("RESULT   = FAILED")
            print("ERROR    = One-request orchestration did not finish the durable goal.")
            return 1
        if recovery_result.supervisor_result is None or "GOAL_COMPLETE" not in recovery_result.supervisor_result.events:
            print("RESULT   = FAILED")
            print("ERROR    = Recovery path did not reach GOAL_COMPLETE.")
            return 1

        first_task_id = result.launch.routed.routed.compiled.plan.tasks[0].task_id
        resumed_events = recovery_result.supervisor_result.events
        resume_index = next((i for i, event in enumerate(resumed_events) if event.startswith("RESUME:")), None)
        if resume_index is None:
            print("RESULT   = FAILED")
            print("ERROR    = Recovery did not record a RESUME event.")
            return 1
        if any(event.startswith(f"RUNNING:{first_task_id}:") for event in resumed_events[resume_index:]):
            print("RESULT   = FAILED")
            print("ERROR    = Completed first task was repeated after handoff.")
            return 1

    print("RESULT   = DONE")
    print("MESSAGE  = V0.8.5 one natural-language request reached GOAL_COMPLETE through durable launch and automatic recovery handoff.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
