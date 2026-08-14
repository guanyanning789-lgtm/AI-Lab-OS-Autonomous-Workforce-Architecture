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
from ai_lab_os.final_entrypoint import FinalNaturalLanguageEntrypoint
from ai_lab_os.models import AgentKind
from ai_lab_os.multi_agent_runtime import MultiAgentRuntimeConfig, build_core_router
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.progress_report import ProgressReportService, render_progress
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy
from ai_lab_os.task_planner import PlannedTaskKind


def _branch(repo: Path) -> str:
    result = subprocess.run(["git", "branch", "--show-current"], cwd=repo, capture_output=True, text=True)
    return (result.stdout or "").strip() or "unknown"


def _check(url: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            response.read(1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"backend unavailable: {url}: {exc}") from exc


def _general_skill() -> SkillContract:
    return SkillContract(
        skill_id="general-research-code-verify",
        name="General Research Code Verify",
        description="Research a technical request, verify the local project, and safely verify the computer path.",
        inputs=(SkillInputSpec("topic", "Natural-language user goal."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        permissions=("web.search", "coding.verify", "computer.mock"),
        metadata={"triggers": "研究,research,检查,檢查,验证,驗證,pytest,代码,代碼,项目,項目,电脑,電腦,computer"},
        steps=(
            SkillStepSpec("research", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Research {topic} and return evidence.", metadata_templates={"query": "{topic}"}),
            SkillStepSpec("coding", PlannedTaskKind.VERIFY, AgentKind.CODING, "Verify the local AI Lab project for {topic}.", depends_on=("research",)),
            SkillStepSpec("computer", PlannedTaskKind.VERIFY, AgentKind.COMPUTER, "Verify the safe computer runtime for {topic}.", depends_on=("coding",), metadata_templates={"action": "click", "args_json": "{}", "window_title": "Notepad", "expected_process": "notepad.exe"}),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Lab V1.0 interactive natural-language CLI")
    parser.add_argument("goal", nargs="+", help="Natural-language goal for AI Lab")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--brain-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--searxng-base-url", default="http://127.0.0.1:8888")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip()
    repo = Path(args.repo).resolve()
    if not goal:
        print("ERROR = goal must not be empty")
        return 2

    try:
        _check(args.brain_base_url.rstrip("/") + "/openapi.json")
        _check(args.searxng_base_url.rstrip("/") + "/search?q=ai-lab&format=json")
    except RuntimeError as exc:
        print(f"ERROR = {exc}")
        return 2

    config = MultiAgentRuntimeConfig(
        repository_path=str(repo),
        branch=_branch(repo),
        tests=("python -m pytest -q",),
        allowed_files=(),
        brain_base_url=args.brain_base_url,
        searxng_base_url=args.searxng_base_url,
        allow_cline_repair=False,
        computer_approved=False,
        computer_dry_run=True,
    )
    router = build_core_router(config)
    registry = SkillRegistry.from_skills((_general_skill(),))

    with tempfile.TemporaryDirectory(prefix="ai-lab-cli-") as temporary:
        store = JsonGoalStore(Path(temporary) / "goals.json")
        history = JsonExecutionHistory(Path(temporary) / "history.jsonl")
        runtime = ProductRuntime(
            registry,
            router.execute,
            store,
            history_store=history,
            launch_policy=SupervisorPolicy(max_cycles=50),
            recovery_policy=SupervisorPolicy(max_cycles=50),
        )
        entry = FinalNaturalLanguageEntrypoint(runtime)
        print("AI LAB V1.0")
        print(f"GOAL = {goal}")
        print("MODE = safe interactive CLI; real Computer actions disabled")
        print()
        result = entry.run(goal)
        report = ProgressReportService(runtime).get(result.goal_id)
        print(render_progress(report))
        print(f"SKILL = {result.skill_id}")
        print(f"RESULT = {'DONE' if report.status == 'complete' else report.status.upper()}")
        return 0 if report.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
