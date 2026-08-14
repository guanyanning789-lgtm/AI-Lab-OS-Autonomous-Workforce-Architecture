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
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy
from ai_lab_os.task_planner import PlannedTaskKind
from ai_lab_os.unified_goal_service import GoalSubmissionRequest


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
        skill_id="product-research-code-computer",
        name="Product Research Code Computer",
        description="Research a technical topic, verify local code, then verify the safe computer runtime.",
        inputs=(SkillInputSpec("topic", "Technical topic to research and verify."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        permissions=("web.search", "coding.verify", "computer.mock"),
        success_criteria=("The ProductRuntime request reaches GOAL_COMPLETE.",),
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
    parser = argparse.ArgumentParser(description="V0.9.5 real ProductRuntime graduation E2E")
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
    print("V0.9.5 REAL PRODUCT RUNTIME E2E")
    print("=" * 78)
    print(f"REQUEST  = {args.request}")
    print(f"REPO     = {repository}")
    print(f"BRANCH   = {branch}")
    print(f"BRAIN    = {args.brain_base_url}")
    print(f"SEARXNG  = {args.searxng_base_url}")
    print("SAFETY   = Computer real actions disabled (approved=false, dry_run=true)")
    print("ENTRY    = ProductRuntime public API only")
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

    with tempfile.TemporaryDirectory(prefix="ai-lab-v095-") as temporary:
        store = JsonGoalStore(Path(temporary) / "goals.json")
        history = JsonExecutionHistory(Path(temporary) / "history.jsonl")
        runtime = ProductRuntime(
            registry,
            router.execute,
            store,
            history_store=history,
            launch_policy=SupervisorPolicy(max_cycles=1),
            recovery_policy=SupervisorPolicy(max_cycles=50),
        )

        submitted = runtime.submit(GoalSubmissionRequest(
            goal=args.request,
            goal_id="v095-real-product-e2e",
        ))
        snapshot = runtime.get_goal(submitted.goal_id)
        events = runtime.get_events(submitted.goal_id)
        tick = runtime.tick()

        print(f"GOAL_ID        = {submitted.goal_id}")
        print(f"SKILL          = {submitted.skill_id}")
        print(f"STATUS         = {submitted.status}")
        print(f"HANDED_OFF     = {submitted.handed_off}")
        print(f"PROGRESS       = {snapshot.progress_percent}%")
        print(f"FINAL_CURSOR   = {snapshot.resume_cursor}")
        print(f"RUNTIME_TICK   = {tick.tick_number}")
        print(f"TICK_ACTIONABLE= {tick.recovery.actionable_goals}")
        print("EVENTS:")
        for event in events:
            print(f"  {event}")

        if submitted.status != "complete" or snapshot.status != "complete":
            print("RESULT   = FAILED")
            print("ERROR    = ProductRuntime did not complete the durable goal.")
            return 1
        if not submitted.handed_off:
            print("RESULT   = FAILED")
            print("ERROR    = Graduation did not exercise automatic recovery handoff.")
            return 1
        if snapshot.progress_percent != 100 or snapshot.resume_cursor is not None:
            print("RESULT   = FAILED")
            print("ERROR    = Final durable snapshot is not fully complete.")
            return 1
        if "GOAL_COMPLETE" not in events:
            print("RESULT   = FAILED")
            print("ERROR    = Product event stream does not contain GOAL_COMPLETE.")
            return 1

        # Completed goals are terminal product objects. Lifecycle controls must
        # fail closed rather than mutate or restart completed work.
        for operation in (runtime.pause, runtime.cancel, runtime.resume):
            try:
                operation(submitted.goal_id)
            except ValueError:
                pass
            else:
                print("RESULT   = FAILED")
                print("ERROR    = Completed goal lifecycle control did not fail closed.")
                return 1

    print("GOAL_COMPLETE")
    print("RESULT   = DONE")
    print("MESSAGE  = V0.9.5 ProductRuntime submitted, recovered, queried and completed one real multi-agent goal through public product boundaries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
