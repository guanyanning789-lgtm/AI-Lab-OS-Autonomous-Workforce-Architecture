from __future__ import annotations

import pytest

from ai_lab_os.coding_executor import CodingExecutor, CodingExecutorConfig
from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind
from ai_lab_os.worker_protocol import WorkerResult


def _task(agent: AgentKind = AgentKind.CODING) -> PlannedTask:
    return PlannedTask(
        task_id="goal-v041-task-002",
        goal_id="goal-v041",
        sequence=2,
        kind=PlannedTaskKind.IMPLEMENT,
        description="Implement the requested feature safely.",
        agent=agent,
        success_criteria=("All configured tests pass",),
        depends_on=("goal-v041-task-001",),
    )


def _config() -> CodingExecutorConfig:
    return CodingExecutorConfig(
        repository_path=r"C:\AI-Lab\brain",
        branch="ai/example",
        tests=("python -m pytest tests/test_example.py -q",),
        allowed_files=("app/example.py",),
        max_attempts=3,
    )


def test_coding_executor_translates_planned_task_to_worker_task() -> None:
    captured = []

    def worker(worker_task):
        captured.append(worker_task)
        return WorkerResult(
            task_id=worker_task.task_id,
            status="complete",
            tests_passed=True,
            attempts_used=2,
            changed_files=["app/example.py"],
        )

    result = CodingExecutor(_config(), worker_runner=worker)(_task())

    assert result.status is TaskExecutionStatus.SUCCESS
    assert len(captured) == 1
    worker_task = captured[0]
    assert worker_task.task_id == "goal-v041-task-002"
    assert worker_task.repository_path == r"C:\AI-Lab\brain"
    assert worker_task.branch == "ai/example"
    assert worker_task.goal == "Implement the requested feature safely."
    assert worker_task.success_criteria == ("All configured tests pass",)
    assert worker_task.allow_cline_repair is True
    assert worker_task.allowed_files == ("app/example.py",)
    assert worker_task.max_attempts == 3
    assert "attempts=2" in result.message


def test_coding_executor_maps_worker_failure_to_supervisor_failure() -> None:
    def worker(worker_task):
        return WorkerResult(
            task_id=worker_task.task_id,
            status="failed",
            tests_passed=False,
            error="verification failed",
        )

    result = CodingExecutor(_config(), worker_runner=worker)(_task())
    assert result.status is TaskExecutionStatus.FAILED
    assert result.message == "verification failed"


def test_coding_executor_fails_closed_for_non_coding_task() -> None:
    called = False

    def worker(worker_task):
        nonlocal called
        called = True
        raise AssertionError("worker must not be called")

    result = CodingExecutor(_config(), worker_runner=worker)(_task(AgentKind.RESEARCH))
    assert result.status is TaskExecutionStatus.FAILED
    assert "cannot execute agent kind" in result.message
    assert called is False


def test_config_requires_allowed_files_when_repair_enabled() -> None:
    with pytest.raises(ValueError, match="allowed_files"):
        CodingExecutorConfig(
            repository_path=r"C:\AI-Lab\brain",
            branch="ai/example",
            tests=("python -m pytest -q",),
            allowed_files=(),
            allow_cline_repair=True,
        )
