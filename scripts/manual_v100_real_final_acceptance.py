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

from ai_lab_os.approval_boundary import ApprovalAwareExecutor, ApprovalService
from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.final_entrypoint import FinalNaturalLanguageEntrypoint
from ai_lab_os.models import AgentKind
from ai_lab_os.multi_agent_runtime import MultiAgentRuntimeConfig, build_core_router
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.product_service import ProductServiceHost
from ai_lab_os.progress_report import ProgressReportService, render_progress
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
        skill_id="v100-final-research-code-computer",
        name="V1.0 Final Research Code Computer",
        description="Research a technical topic, verify local code, then perform one explicitly approved computer action.",
        inputs=(SkillInputSpec("topic", "Technical goal to complete."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        permissions=("web.search", "coding.verify", "computer.real"),
        success_criteria=("The final V1.0 product request reaches GOAL_COMPLETE.",),
        metadata={"triggers": "research,研究,pytest,验证,驗證,电脑,電腦,computer,click"},
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
                "Perform the final approved safe computer verification for {topic}.",
                depends_on=("coding",),
                metadata_templates={
                    "action": "click",
                    "args_json": "{\"target\":\"100,100\"}",
                    "window_title": "Notepad",
                    "expected_process": "notepad.exe",
                },
            ),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Lab V1.0 real final acceptance graduation")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--brain-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--searxng-base-url", default="http://127.0.0.1:8888")
    parser.add_argument("--request", default="请研究 pytest fixture，验证本地代码，并完成最终电脑执行链验收")
    parser.add_argument("--approve", action="store_true", help="Explicitly approve the one real Computer action after the runtime stops at approval_required.")
    args = parser.parse_args()

    repository = Path(args.repo).resolve()
    branch = current_branch(repository)
    print("=" * 78)
    print("AI LAB V1.0 REAL FINAL ACCEPTANCE")
    print("=" * 78)
    print(f"REQUEST  = {args.request}")
    print(f"REPO     = {repository}")
    print(f"BRANCH   = {branch}")
    print(f"BRAIN    = {args.brain_base_url}")
    print(f"SEARXNG  = {args.searxng_base_url}")
    print("ENTRY    = FinalNaturalLanguageEntrypoint")
    print("SAFETY   = Real Computer action is fail-closed until --approve is explicitly supplied")
    print("ACTION   = Notepad-only click target 100,100; Brain foreground/process guards remain mandatory")
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
        repository_path=str(repository), branch=branch,
        tests=("python -m pytest tests/test_agent_router_v035.py -q",), allowed_files=(),
        brain_base_url=args.brain_base_url, searxng_base_url=args.searxng_base_url,
        allow_cline_repair=False, computer_approved=True, computer_dry_run=False,
    )
    router = build_core_router(config)

    with tempfile.TemporaryDirectory(prefix="ai-lab-v100-") as temporary:
        store = JsonGoalStore(Path(temporary) / "goals.json")
        history = JsonExecutionHistory(Path(temporary) / "history.jsonl")
        approvals = ApprovalService(store)

        def runtime_factory() -> ProductRuntime:
            gated = ApprovalAwareExecutor(router.execute, approvals, real_computer_actions_enabled=True)
            return ProductRuntime(
                registry, gated, store, history_store=history,
                launch_policy=SupervisorPolicy(max_cycles=50),
                recovery_policy=SupervisorPolicy(max_cycles=50), approval_service=approvals,
            )

        host = ProductServiceHost(runtime_factory)
        host.start(recover=False)
        entry = FinalNaturalLanguageEntrypoint(host.runtime)
        first = entry.run(args.request, goal_id="v100-real-final-acceptance")
        report_service = ProgressReportService(host.runtime)
        waiting = report_service.get(first.goal_id)
        print(render_progress(waiting))
        print()

        if first.status != "approval_required" or waiting.status != "approval_required":
            print("RESULT   = FAILED")
            print("ERROR    = Final acceptance did not stop at explicit approval boundary.")
            return 1
        task_id = waiting.current_task
        if not task_id:
            print("RESULT   = FAILED")
            print("ERROR    = Approval-required goal has no current task.")
            return 1
        print(f"APPROVAL_REQUIRED = {task_id}")
        print("REAL_ACTION       = click Notepad at 100,100")
        if not args.approve:
            print("RESULT   = APPROVAL_REQUIRED")
            print("NEXT     = Re-run the exact command with --approve after reviewing the action above.")
            return 3

        host.runtime.approve(first.goal_id, task_id)
        print(f"APPROVED          = {task_id}")
        tick = host.runtime.tick()
        final_report = report_service.get(first.goal_id)
        print()
        print(render_progress(final_report))
        print(f"RUNTIME_TICK      = {tick.tick_number}")
        print(f"TICK_ACTIONABLE   = {tick.recovery.actionable_goals}")
        final_snapshot = host.runtime.get_goal(first.goal_id)
        if final_snapshot.status != "complete":
            print("RESULT   = FAILED")
            print("ERROR    = Goal did not complete after explicit approval.")
            return 1
        if final_snapshot.progress_percent != 100 or final_snapshot.resume_cursor is not None:
            print("RESULT   = FAILED")
            print("ERROR    = Final durable snapshot is not 100% complete.")
            return 1
        if "GOAL_COMPLETE" not in final_snapshot.events:
            print("RESULT   = FAILED")
            print("ERROR    = Final event stream does not contain GOAL_COMPLETE.")
            return 1

        health_before = host.health()
        host.restart(recover=True)
        health_after = host.health()
        restarted = host.runtime.get_goal(first.goal_id)
        if restarted.status != "complete" or restarted.progress_percent != 100:
            print("RESULT   = FAILED")
            print("ERROR    = Completed durable goal did not survive service restart.")
            return 1
        print(f"SERVICE_GENERATION = {health_before.generation}->{health_after.generation}")
        print("GOAL_COMPLETE")
        print("PROGRESS = 100%")
        print("RESULT   = DONE")
        print("MESSAGE  = V1.0 final acceptance passed: one natural-language goal ran autonomously, paused only for explicit real-action approval, resumed through ProductRuntime, completed, reported 100%, and survived service restart.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
