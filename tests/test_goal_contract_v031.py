import json

import pytest

from ai_lab_os.goal_contract import (
    GoalContract,
    GoalPriority,
    GoalStatus,
    load_goal_contract,
    write_goal_contract,
)


def test_goal_contract_normalizes_and_serializes() -> None:
    contract = GoalContract(
        goal_id=" goal-0001 ",
        natural_language_goal=" Build the supervisor runtime. ",
        success_criteria=(" Planner creates tasks. ", " Goal can complete. "),
        constraints=(" Do not bypass approval. ",),
        priority=GoalPriority.HIGH,
        metadata={"source": "chatgpt"},
    )

    assert contract.goal_id == "goal-0001"
    assert contract.natural_language_goal == "Build the supervisor runtime."
    assert contract.success_criteria == ("Planner creates tasks.", "Goal can complete.")
    assert contract.status is GoalStatus.RECEIVED
    assert contract.to_dict() == {
        "goal_id": "goal-0001",
        "natural_language_goal": "Build the supervisor runtime.",
        "success_criteria": ["Planner creates tasks.", "Goal can complete."],
        "constraints": ["Do not bypass approval."],
        "priority": "high",
        "status": "received",
        "metadata": {"source": "chatgpt"},
    }


def test_goal_contract_round_trip_file(tmp_path) -> None:
    path = tmp_path / "goals" / "goal-0002.json"
    original = GoalContract(
        goal_id="goal-0002",
        natural_language_goal="Repair a failing feature and verify it.",
        success_criteria=("Targeted tests pass", "Regression tests pass"),
        constraints=("Only modify allowed files",),
    )

    write_goal_contract(path, original)
    loaded = load_goal_contract(path)

    assert loaded == original
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["priority"] == "normal"
    assert raw["status"] == "received"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"goal_id": " ", "natural_language_goal": "x", "success_criteria": ("done",)}, "goal_id"),
        ({"goal_id": "g", "natural_language_goal": " ", "success_criteria": ("done",)}, "natural_language_goal"),
        ({"goal_id": "g", "natural_language_goal": "x", "success_criteria": ()}, "success_criteria"),
        ({"goal_id": "g", "natural_language_goal": "x", "success_criteria": ("done", "done")}, "duplicates"),
        (
            {
                "goal_id": "g",
                "natural_language_goal": "x",
                "success_criteria": ("done",),
                "constraints": ("safe", "safe"),
            },
            "duplicates",
        ),
    ],
)
def test_goal_contract_rejects_invalid_contracts(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        GoalContract(**kwargs)


def test_from_dict_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="unknown goal contract fields"):
        GoalContract.from_dict(
            {
                "goal_id": "goal-1",
                "natural_language_goal": "Do the task",
                "success_criteria": ["Done"],
                "unexpected": True,
            }
        )


def test_from_dict_rejects_invalid_enums_and_shapes() -> None:
    base = {
        "goal_id": "goal-1",
        "natural_language_goal": "Do the task",
        "success_criteria": ["Done"],
    }

    with pytest.raises(ValueError, match="invalid goal priority"):
        GoalContract.from_dict({**base, "priority": "urgent"})

    with pytest.raises(ValueError, match="invalid goal status"):
        GoalContract.from_dict({**base, "status": "waiting_for_magic"})

    with pytest.raises(ValueError, match="success_criteria must be a list of strings"):
        GoalContract.from_dict({**base, "success_criteria": "Done"})


def test_goal_status_supports_supervisor_lifecycle() -> None:
    assert [status.value for status in GoalStatus] == [
        "received",
        "planning",
        "active",
        "blocked",
        "failed",
        "complete",
    ]
