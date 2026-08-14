from __future__ import annotations

from dataclasses import dataclass

from ai_lab_os.agent_router import AgentRouter
from ai_lab_os.coding_executor import CodingExecutor, CodingExecutorConfig
from ai_lab_os.computer_executor import ComputerExecutor, HttpComputerBackend
from ai_lab_os.research_executor import ResearchExecutor, SearXNGResearchClient
from ai_lab_os.supervisor_loop import SupervisorPolicy, SupervisorRunResult, run_supervisor_loop
from ai_lab_os.task_planner import TaskPlanContract


@dataclass(frozen=True)
class MultiAgentRuntimeConfig:
    repository_path: str
    branch: str
    tests: tuple[str, ...]
    allowed_files: tuple[str, ...]
    brain_base_url: str = "http://127.0.0.1:8000"
    computer_path: str = "/task/windows/e2e"
    searxng_base_url: str = "http://127.0.0.1:8080"
    allow_cline_repair: bool = True
    coding_max_attempts: int = 2
    research_max_sources: int = 5
    computer_approved: bool = False
    computer_dry_run: bool = True


def build_core_router(
    config: MultiAgentRuntimeConfig,
    *,
    coding_executor: CodingExecutor | None = None,
    research_executor: ResearchExecutor | None = None,
    computer_executor: ComputerExecutor | None = None,
) -> AgentRouter:
    """Compose Coding, Research, and Computer executors behind one router."""

    coding = coding_executor or CodingExecutor(
        CodingExecutorConfig(
            repository_path=config.repository_path,
            branch=config.branch,
            tests=config.tests,
            allowed_files=config.allowed_files,
            allow_cline_repair=config.allow_cline_repair,
            max_attempts=config.coding_max_attempts,
        )
    )
    research = research_executor or ResearchExecutor(
        SearXNGResearchClient(base_url=config.searxng_base_url),
        max_sources=config.research_max_sources,
    )
    computer = computer_executor or ComputerExecutor(
        HttpComputerBackend(
            base_url=config.brain_base_url,
            path=config.computer_path,
        ),
        approved=config.computer_approved,
        dry_run=config.computer_dry_run,
    )
    return AgentRouter.with_core_agents(
        coding=coding,
        research=research,
        computer=computer,
    )


def run_multi_agent_plan(
    plan: TaskPlanContract,
    config: MultiAgentRuntimeConfig,
    *,
    router: AgentRouter | None = None,
    policy: SupervisorPolicy | None = None,
) -> SupervisorRunResult:
    """Run a plan through Supervisor -> AgentRouter -> executor adapters."""

    active_router = router or build_core_router(config)
    return run_supervisor_loop(plan, active_router.execute, policy=policy)
