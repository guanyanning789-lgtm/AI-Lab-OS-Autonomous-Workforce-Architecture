from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ai_lab_os.local_worker import run_task
from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask
from ai_lab_os.worker_protocol import WorkerResult, WorkerTask


WorkerRunner = Callable[[WorkerTask], WorkerResult]


@dataclass(frozen=True)
class CodingExecutorConfig:
    repository_path: str
    branch: str
    tests: tuple[str, ...]
    allowed_files: tuple[str, ...]
    allow_cline_repair: bool = True
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if not self.repository_path.strip():
            raise ValueError("repository_path cannot be empty")
        if not self.branch.strip():
            raise ValueError("branch cannot be empty")
        if not self.tests:
            raise ValueError("tests cannot be empty")
        if self.allow_cline_repair and not self.allowed_files:
            raise ValueError("allowed_files are required when Cline repair is enabled")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")


class CodingExecutor:
    """Bridge Supervisor PlannedTask execution into the proven local coding worker."""

    def __init__(
        self,
        config: CodingExecutorConfig,
        *,
        worker_runner: WorkerRunner | None = None,
    ) -> None:
        self.config = config
        self.worker_runner = worker_runner or run_task

    def __call__(self, task: PlannedTask) -> TaskExecutionResult:
        if task.agent is not AgentKind.CODING:
            return TaskExecutionResult(
                status=TaskExecutionStatus.FAILED,
                message=f"CodingExecutor cannot execute agent kind: {task.agent.value}",
            )

        worker_task = WorkerTask(
            task_id=task.task_id,
            repository_path=self.config.repository_path,
            branch=self.config.branch,
            goal=task.description,
            success_criteria=task.success_criteria,
            tests=self.config.tests,
            allow_cline_repair=self.config.allow_cline_repair,
            allowed_files=self.config.allowed_files,
            max_attempts=self.config.max_attempts,
        )
        result = self.worker_runner(worker_task)

        if result.status == "complete" and result.tests_passed:
            evidence = ", ".join(result.changed_files) or "no allowed-file change required"
            return TaskExecutionResult(
                status=TaskExecutionStatus.SUCCESS,
                message=f"coding worker complete; changed={evidence}; attempts={result.attempts_used}",
            )

        detail = result.error or result.brain_message or "coding worker failed"
        return TaskExecutionResult(
            status=TaskExecutionStatus.FAILED,
            message=detail,
        )
