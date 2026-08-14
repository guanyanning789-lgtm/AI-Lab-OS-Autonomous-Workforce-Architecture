from __future__ import annotations

from ai_lab_os.computer_executor import ComputerActionRequest, ComputerExecutor
from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind


class FakeBackend:
    def __init__(self, response: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.response = response or {"success": True, "message": "ok"}
        self.error = error
        self.requests: list[ComputerActionRequest] = []

    def execute(self, request: ComputerActionRequest) -> dict[str, object]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return dict(self.response)


def _task(agent: AgentKind = AgentKind.COMPUTER) -> PlannedTask:
    return PlannedTask(
        task_id="task-computer-001",
        goal_id="goal-computer",
        sequence=1,
        kind=PlannedTaskKind.VERIFY,
        description="Open the result and verify the expected text is visible.",
        agent=agent,
        success_criteria=("Expected text is visible.",),
        metadata={"window_title": "Notepad"},
    )


def test_computer_executor_uses_safe_defaults_and_forwards_task_contract() -> None:
    backend = FakeBackend()
    executor = ComputerExecutor(backend=backend)

    result = executor(_task())

    assert result.status is TaskExecutionStatus.SUCCESS
    assert result.message == "ok"
    assert len(backend.requests) == 1
    request = backend.requests[0]
    assert request.task_id == "task-computer-001"
    assert request.instruction.startswith("Open the result")
    assert request.success_criteria == ("Expected text is visible.",)
    assert request.metadata == {"window_title": "Notepad"}
    assert request.approved is False
    assert request.dry_run is True


def test_computer_executor_can_explicitly_enable_real_execution() -> None:
    backend = FakeBackend()
    executor = ComputerExecutor(backend=backend, approved=True, dry_run=False)

    result = executor(_task())

    assert result.status is TaskExecutionStatus.SUCCESS
    request = backend.requests[0]
    assert request.approved is True
    assert request.dry_run is False


def test_computer_executor_maps_backend_failure() -> None:
    backend = FakeBackend(response={"success": False, "message": "verification failed"})
    result = ComputerExecutor(backend=backend)(_task())

    assert result.status is TaskExecutionStatus.FAILED
    assert result.message == "verification failed"


def test_computer_executor_maps_backend_exception_to_failed_result() -> None:
    backend = FakeBackend(error=RuntimeError("host unavailable"))
    result = ComputerExecutor(backend=backend)(_task())

    assert result.status is TaskExecutionStatus.FAILED
    assert "host unavailable" in result.message


def test_computer_executor_fails_closed_for_non_computer_task() -> None:
    backend = FakeBackend()
    result = ComputerExecutor(backend=backend)(_task(AgentKind.CODING))

    assert result.status is TaskExecutionStatus.FAILED
    assert "refuses non-computer agent" in result.message
    assert backend.requests == []
