from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_lab_os.goal_contract import GoalPriority
from ai_lab_os.goal_intake import GoalIntakeRequest, intake_goal


def test_intake_generates_stable_goal_contract_defaults() -> None:
    result = intake_goal(
        GoalIntakeRequest(request="Research pytest fixtures"),
        now=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )
    assert result.contract.goal_id == "goal-20260814-120000-research-pytest-fixtures"
    assert result.contract.natural_language_goal == "Research pytest fixtures"
    assert result.contract.success_criteria == (
        "The requested outcome is completed and verified with evidence.",
    )
    assert result.contract.metadata["intake_source"] == "natural_language"
    assert result.contract.metadata["intake_version"] == "0.8.1"
    assert result.generated_goal_id is True
    assert result.generated_success_criteria is True


def test_intake_preserves_explicit_goal_fields() -> None:
    result = intake_goal(
        GoalIntakeRequest(
            request="Verify local runtime",
            goal_id="goal-explicit",
            success_criteria=("pytest passes",),
            constraints=("no real desktop actions",),
            priority=GoalPriority.HIGH,
            metadata={"source": "test"},
        ),
        now=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )
    contract = result.contract
    assert contract.goal_id == "goal-explicit"
    assert contract.success_criteria == ("pytest passes",)
    assert contract.constraints == ("no real desktop actions",)
    assert contract.priority is GoalPriority.HIGH
    assert contract.metadata["source"] == "test"
    assert result.generated_goal_id is False
    assert result.generated_success_criteria is False


def test_intake_rejects_empty_request() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        GoalIntakeRequest(request="   ")


def test_intake_rejects_duplicate_constraints() -> None:
    with pytest.raises(ValueError, match="constraints cannot contain duplicates"):
        intake_goal(GoalIntakeRequest(request="x", constraints=("safe", "safe")))
