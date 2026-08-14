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
from ai_lab_os.recovery_daemon import RecoveryDaemonConfig, run_recovery_daemon
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.skill_selector import route_skill_request
from ai_lab_os.supervisor_loop import SupervisorPolicy, run_supervisor_loop
from ai_lab_os.task_planner import PlannedTaskKind


def current_branch(repository: Path) -> str:
    completed = subprocess.run(["git", "branch", "--show-current"], cwd=str(repository), capture_output=True, text=True, check=False)
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
        skill_id="autonomous-recovery-research-code-verify",
        name="Autonomous Recovery Research Code Verify",
        description="Research a topic, verify code, then verify the safe computer runtime after autonomous daemon recovery.",
        inputs=(SkillInputSpec("topic", "Technical topic to research and verify."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        permissions=("web.search", "coding.verify", "computer.mock"),
        success_criteria=("Daemon discovers unfinished durable goal and reaches GOAL_COMPLETE without manual resume.",),
        metadata={"triggers": "research,研究,recovery,恢复,pytest"},
        steps=(
            SkillStepSpec("research", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Research {topic} and return evidence.", metadata_templates={"query": "{topic}"}),
            SkillStepSpec("coding", PlannedTaskKind.VERIFY, AgentKind.CODING, "Verify local AI Lab routing for {topic}.", depends_on=("research",)),
            SkillStepSpec("computer", PlannedTaskKind.VERIFY, AgentKind.COMPUTER, "Verify safe computer runtime for {topic}.", depends_on=("coding",), metadata_templates={"action": "click", "args_json": "{}", "window_title": "Notepad", "expected_process": "notepad.exe"}),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="V0.7.5 real autonomous recovery graduation E2E")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--brain-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--searxng-base-url", default="http://127.0.0.1:8888")
    parser.add_argument("--request", default="请研究 pytest fixture，并让系统自动恢复后完成代码和电脑验证")
    args = parser.parse_args()

    repository = Path(args.repo).resolve()
    branch = current_branch(repository)
    print("=" * 78)
    print("V0.7.5 REAL AUTONOMOUS RECOVERY E2E")
    print("=" * 78)
    print(f"REQUEST  = {args.request}")
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
    routed = route_skill_request(args.request, registry, goal_id="v075-autonomous-recovery-e2e")
    plan = routed.compiled.plan
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

    with tempfile.TemporaryDirectory(prefix="ai-lab-v075-") as temporary:
        state_path = Path(temporary) / "goals.json"
        history_path = Path(temporary) / "history.jsonl"
        store = JsonGoalStore(state_path)
        history = JsonExecutionHistory(history_path)
        router = build_core_router(config)

        print("PHASE 1  = Run one task only, persist unfinished goal, then stop")
        phase1 = run_supervisor_loop(
            plan,
            router.execute,
            policy=SupervisorPolicy(max_cycles=1),
            goal_store=store,
            history_store=history,
        )
        persisted = store.load(plan.goal_id)
        first_task_id = plan.tasks[0].task_id
        print(f"PHASE1_STATUS = {phase1.status}")
        print(f"RESUME_CURSOR = {persisted.resume_cursor}")
        if persisted.tasks[0].status != "complete":
            print("RESULT   = FAILED")
            print("ERROR    = Phase 1 did not persist Task 1 as complete.")
            return 1

        print()
        print("PHASE 2  = Start Recovery Daemon only; no manual resume call")
        router_after_stop = build_core_router(config)
        reports = run_recovery_daemon(
            router_after_stop.execute,
            store,
            config=RecoveryDaemonConfig(poll_seconds=0.1, max_scans=1),
            supervisor_policy=SupervisorPolicy(max_cycles=50),
            history_store=history,
            sleep_fn=lambda _: None,
        )
        final = store.load(plan.goal_id)
        report = reports[0]
        recovery_result = next(item for item in report.results if item.goal_id == plan.goal_id)
        supervisor_result = recovery_result.supervisor_result
        print(f"SCAN          = {report.scan_number}")
        print(f"ACTIONABLE    = {report.actionable_goals}")
        print(f"DECISION      = {recovery_result.decision.action.value}")
        print(f"STATUS        = {recovery_result.status}")
        print(f"FINAL_CURSOR  = {final.resume_cursor}")
        if supervisor_result is not None:
            print("EVENTS:")
            for event in supervisor_result.events:
                print(f"  {event}")

        if final.status != "complete" or final.resume_cursor is not None:
            print("RESULT   = FAILED")
            print("ERROR    = Recovery Daemon did not complete the persisted goal.")
            return 1
        if supervisor_result is None or "GOAL_COMPLETE" not in supervisor_result.events:
            print("RESULT   = FAILED")
            print("ERROR    = Autonomous recovery did not reach GOAL_COMPLETE.")
            return 1
        post_resume = supervisor_result.events[supervisor_result.events.index(next(e for e in supervisor_result.events if e.startswith("RESUME:"))):]
        if any(event.startswith(f"RUNNING:{first_task_id}:") for event in post_resume):
            print("RESULT   = FAILED")
            print("ERROR    = Completed Task 1 was re-executed after autonomous recovery.")
            return 1

    print("RESULT   = DONE")
    print("MESSAGE  = V0.7.5 daemon discovered and completed the durable goal without manual resume.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
