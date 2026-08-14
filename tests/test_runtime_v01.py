import pytest

from ai_lab_os.models import AgentKind, Goal, TaskPlan, TaskStatus, TaskStep
from ai_lab_os.runtime import TaskState, ToolRouter


def build_plan() -> TaskPlan:
    return TaskPlan(
        goal=Goal("Fix a failing coding task", ("tests pass",)),
        steps=(
            TaskStep(1, "Inspect failure", AgentKind.RESEARCH),
            TaskStep(2, "Modify code", AgentKind.CODING),
            TaskStep(3, "Verify result", AgentKind.CODING),
        ),
    )


def test_task_state_completes_in_order():
    state = TaskState(build_plan())
    state.start()

    assert state.status == TaskStatus.RUNNING
    assert state.current_step == 1

    state.complete_step(1)
    state.complete_step(2)
    state.complete_step(3)

    assert state.status == TaskStatus.COMPLETE
    assert state.completed_steps == [1, 2, 3]


def test_task_state_rejects_out_of_order_completion():
    state = TaskState(build_plan())
    state.start()

    with pytest.raises(ValueError, match="current step"):
        state.complete_step(2)


def test_task_state_records_failure_and_retry_count():
    state = TaskState(build_plan())
    state.start()
    state.fail_step(1)

    assert state.status == TaskStatus.FAILED
    assert state.failed_steps == [1]
    assert state.retry_counts[1] == 1


def test_tool_router_resolves_registered_provider():
    router = ToolRouter()
    router.register(AgentKind.CODING, "cline")

    assert router.resolve(AgentKind.CODING) == "cline"


def test_tool_router_rejects_missing_provider():
    router = ToolRouter()

    with pytest.raises(LookupError):
        router.resolve(AgentKind.COMPUTER)
