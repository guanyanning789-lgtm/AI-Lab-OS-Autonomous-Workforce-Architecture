from __future__ import annotations

from ai_lab_os.computer_executor import BrainWindowsE2EBackend, ComputerActionRequest, ComputerExecutor
from ai_lab_os.models import AgentKind
from ai_lab_os.multi_agent_runtime import MultiAgentRuntimeConfig, build_core_router, run_multi_agent_plan
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract


class RecordingExecutor:
    def __init__(self, label: str, calls: list[str]) -> None:
        self.label = label
        self.calls = calls

    def __call__(self, task: PlannedTask) -> TaskExecutionResult:
        self.calls.append(f"{self.label}:{task.task_id}")
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, self.label)


class CapturingBrainBackend(BrainWindowsE2EBackend):
    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:8000")
        self.payloads: list[dict[str, object]] = []

    def _post(self, payload: dict[str, object]) -> dict[str, object]:
        self.payloads.append(payload)
        return {"ok": True, "status": "completed", "errors": []}


def _config() -> MultiAgentRuntimeConfig:
    return MultiAgentRuntimeConfig(
        repository_path=r"C:\AI-Lab\brain",
        branch="ai/test",
        tests=("python -m pytest -q",),
        allowed_files=("app/main.py",),
    )


def _plan() -> TaskPlanContract:
    goal_id = "goal-v044"
    research = PlannedTask(
        task_id="research-1",
        goal_id=goal_id,
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description="Research the required implementation evidence.",
        agent=AgentKind.RESEARCH,
    )
    coding = PlannedTask(
        task_id="coding-1",
        goal_id=goal_id,
        sequence=2,
        kind=PlannedTaskKind.IMPLEMENT,
        description="Implement the change.",
        agent=AgentKind.CODING,
        depends_on=(research.task_id,),
    )
    computer = PlannedTask(
        task_id="computer-1",
        goal_id=goal_id,
        sequence=3,
        kind=PlannedTaskKind.VERIFY,
        description="Verify the result on Windows.",
        agent=AgentKind.COMPUTER,
        depends_on=(coding.task_id,),
        metadata={"action": "click"},
    )
    return TaskPlanContract(goal_id=goal_id, tasks=(research, coding, computer))


def test_build_core_router_registers_all_three_agent_kinds() -> None:
    calls: list[str] = []
    router = build_core_router(
        _config(),
        coding_executor=RecordingExecutor("coding", calls),  # type: ignore[arg-type]
        research_executor=RecordingExecutor("research", calls),  # type: ignore[arg-type]
        computer_executor=RecordingExecutor("computer", calls),  # type: ignore[arg-type]
    )

    assert router.supports(AgentKind.CODING)
    assert router.supports(AgentKind.RESEARCH)
    assert router.supports(AgentKind.COMPUTER)


def test_multi_agent_plan_routes_research_coding_computer_in_dependency_order() -> None:
    calls: list[str] = []
    router = build_core_router(
        _config(),
        coding_executor=RecordingExecutor("coding", calls),  # type: ignore[arg-type]
        research_executor=RecordingExecutor("research", calls),  # type: ignore[arg-type]
        computer_executor=RecordingExecutor("computer", calls),  # type: ignore[arg-type]
    )

    result = run_multi_agent_plan(_plan(), _config(), router=router)

    assert result.status == "complete"
    assert result.completed_tasks == ("research-1", "coding-1", "computer-1")
    assert result.events[-1] == "GOAL_COMPLETE"
    assert calls == [
        "research:research-1",
        "coding:coding-1",
        "computer:computer-1",
    ]


def test_default_runtime_uses_brain_windows_e2e_backend_with_safe_defaults() -> None:
    router = build_core_router(_config())
    executor = router.executor_for(AgentKind.COMPUTER)

    assert isinstance(executor, ComputerExecutor)
    assert isinstance(executor.backend, BrainWindowsE2EBackend)
    assert executor.approved is False
    assert executor.dry_run is True


def test_brain_windows_backend_maps_task_to_verified_contract_in_safe_mode() -> None:
    backend = CapturingBrainBackend()
    response = backend.execute(
        ComputerActionRequest(
            task_id="computer-safe",
            instruction="Mock click only",
            success_criteria=("accepted",),
            metadata={
                "action": "click",
                "args_json": '{"x": 10, "y": 20}',
                "window_title": "Notepad",
            },
            approved=False,
            dry_run=True,
        )
    )

    assert response["status"] == "completed"
    payload = backend.payloads[0]
    assert payload["task_id"] == "computer-safe"
    assert payload["mock"] is True
    assert payload["allow_real_actions"] is False
    step = payload["steps"][0]  # type: ignore[index]
    assert step["action"] == "click"  # type: ignore[index]
    assert step["args"] == {"x": 10, "y": 20}  # type: ignore[index]
    assert step["window_title"] == "Notepad"  # type: ignore[index]


def test_brain_windows_backend_refuses_unknown_action_before_http() -> None:
    backend = CapturingBrainBackend()
    try:
        backend.execute(
            ComputerActionRequest(
                task_id="bad-action",
                instruction="Do not run",
                success_criteria=(),
                metadata={"action": "drag"},
            )
        )
    except RuntimeError as exc:
        assert "click, type, hotkey" in str(exc)
    else:
        raise AssertionError("unsupported action should fail closed")

    assert backend.payloads == []
