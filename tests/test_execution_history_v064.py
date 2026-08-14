from __future__ import annotations

from ai_lab_os.execution_history import ExecutionHistoryRecord, JsonExecutionHistory
from ai_lab_os.persistent_goal_store import PersistentGoalState, PersistentTaskState


def _state(*, goal_id: str = "goal-history", status: str = "complete") -> PersistentGoalState:
    return PersistentGoalState(
        goal_id=goal_id,
        status=status,
        plan={
            "goal_id": goal_id,
            "planner_version": "v0.5.3-skill-compiler",
            "tasks": [
                {"task_id": "t1", "metadata": {"skill_id": "research-code-verify"}},
                {"task_id": "t2", "metadata": {"skill_id": "research-code-verify"}},
            ],
        },
        tasks=(
            PersistentTaskState("t1", status="complete", attempts=2, evidence=("source-a",)),
            PersistentTaskState("t2", status="complete" if status == "complete" else "replan", attempts=1, evidence=("test-pass",)),
        ),
        resume_cursor=None if status == "complete" else "t2",
        cycles=3,
        events=("RUNNING:t1:attempt=1", "COMPLETE:t1", "GOAL_COMPLETE") if status == "complete" else ("REPLAN:t2",),
        schema_version="0.6.2",
    )


def test_history_record_summarizes_persistent_goal() -> None:
    record = ExecutionHistoryRecord.from_goal_state(_state())
    assert record.goal_id == "goal-history"
    assert record.skill_id == "research-code-verify"
    assert record.status == "complete"
    assert record.completed_tasks == ("t1", "t2")
    assert record.failed_tasks == ()
    assert record.total_attempts == 3
    assert record.evidence == ("source-a", "test-pass")


def test_history_store_appends_and_filters(tmp_path) -> None:
    history = JsonExecutionHistory(tmp_path / "history.jsonl")
    history.append_goal_state(_state(goal_id="goal-a"))
    history.append_goal_state(_state(goal_id="goal-b", status="replan_required"))

    assert [item.goal_id for item in history.list(skill_id="research-code-verify")] == ["goal-a", "goal-b"]
    assert [item.goal_id for item in history.list(status="complete")] == ["goal-a"]
    assert history.latest(goal_id="goal-b").failed_tasks == ("t2",)


def test_history_store_is_append_only(tmp_path) -> None:
    history = JsonExecutionHistory(tmp_path / "history.jsonl")
    history.append_goal_state(_state(goal_id="same"))
    history.append_goal_state(_state(goal_id="same", status="replan_required"))

    records = history.list(goal_id="same")
    assert len(records) == 2
    assert records[0].status == "complete"
    assert records[1].status == "replan_required"


def test_history_latest_fails_closed_when_empty(tmp_path) -> None:
    history = JsonExecutionHistory(tmp_path / "history.jsonl")
    try:
        history.latest(goal_id="missing")
    except LookupError as exc:
        assert "execution history record not found" in str(exc)
    else:
        raise AssertionError("expected LookupError")
