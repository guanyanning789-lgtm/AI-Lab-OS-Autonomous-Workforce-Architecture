from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.models import AgentKind
from ai_lab_os.multi_agent_runtime import MultiAgentRuntimeConfig, run_multi_agent_plan
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.skill_selector import route_skill_request
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
        skill_id="research-code-verify",
        name="Research Code Verify",
        description="Research a technical topic, verify the local code tests, then verify through the computer runtime.",
        inputs=(SkillInputSpec("topic", "Technical topic to research and verify."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        permissions=("web.search", "coding.verify", "computer.mock"),
        success_criteria=("Each step completes successfully.",),
        metadata={"triggers": "research,研究,verify,验证,pytest"},
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
                description_template="Verify the local AI Lab OS routing regression for {topic}.",
                depends_on=("research",),
                success_criteria=("Configured pytest command passes.",),
            ),
            SkillStepSpec(
                step_id="computer",
                kind=PlannedTaskKind.VERIFY,
                agent=AgentKind.COMPUTER,
                description_template="Verify the safe computer runtime after researching {topic}.",
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
    parser = argparse.ArgumentParser(description="V0.5.5 real natural-language Skill graduation E2E")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--brain-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--searxng-base-url", default="http://127.0.0.1:8888")
    parser.add_argument(
        "--request",
        default="请帮我研究 pytest fixture，并验证本地代码和电脑执行链是否正常",
    )
    args = parser.parse_args()

    repository = Path(args.repo).resolve()
    branch = current_branch(repository)
    print("=" * 78)
    print("V0.5.5 REAL NATURAL-LANGUAGE SKILL E2E")
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
    routed = route_skill_request(
        args.request,
        registry,
        goal_id="v055-real-skill-e2e",
    )
    print(f"SKILL    = {routed.selection.skill.skill_id}")
    print(f"SCORE    = {routed.selection.score}")
    print(f"MATCHES  = {', '.join(routed.selection.matched_terms)}")
    print(f"INPUTS   = {routed.extracted_inputs}")
    print(f"TASKS    = {len(routed.compiled.plan.tasks)}")
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
    result = run_multi_agent_plan(routed.compiled.plan, config)

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
        print("MESSAGE  = V0.5.5 natural-language Skill E2E reached GOAL_COMPLETE.")
        return 0

    print("RESULT   = FAILED")
    print("ERROR    = Skill graduation E2E did not reach GOAL_COMPLETE.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
