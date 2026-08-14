from __future__ import annotations

import pytest

from ai_lab_os.goal_query_service import GoalStatusSnapshot, GoalTaskSnapshot
from ai_lab_os.progress_report import ProgressReportService, render_progress


def _snapshot(*, status="in_progress", progress=50, cursor="task-2", events=("COMPLETE:task-1", "RESUME:task-2"), last_error=None):
    return GoalStatusSnapshot(
        goal_id="goal-report",
        status=status,
        resume_cursor=cursor,
        cycles=2,
        completed_tasks=1 if progress < 100 else 2,
        total_tasks=2,
        progress_percent=progress,
        last_error=last_error,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:01+00:00",
        tasks=(
            GoalTaskSnapshot("task-1", "complete", 1, "", ()),
            GoalTaskSnapshot("task-2", "ready" if status != "complete" else "complete", 1, last_error or "", ()),
        ),
        events=events,
    )


def test_report_exposes_user_facing_progress_and_recovery() -> None:
    report = ProgressReportService.from_snapshot(_snapshot())
    assert report.progress_percent == 50
    assert report.current_task == "task-2"
    assert report.recovery_count == 1
    assert report.recovering is True
    assert report.last_event == "RESUME:task-2"
    assert report.final_result is None


def test_complete_report_has_terminal_result_and_no_current_task() -> None:
    report = ProgressReportService.from_snapshot(
        _snapshot(status="complete", progress=100, cursor=None, events=("COMPLETE:task-2", "GOAL_COMPLETE"))
    )
    assert report.progress_percent == 100
    assert report.current_task is None
    assert report.recovering is False
    assert report.final_result == "GOAL_COMPLETE"


def test_renderer_is_stable_and_does_not_clear_terminal() -> None:
    report = ProgressReportService.from_snapshot(_snapshot())
    text = render_progress(report, width=10)
    assert "PROGRESS  = [#####-----] 50%" in text
    assert "CURRENT   = task-2" in text
    assert "RECOVERY  = 1 (active)" in text
    assert "\x1b" not in text


def test_renderer_shows_error_and_validates_width() -> None:
    report = ProgressReportService.from_snapshot(_snapshot(status="blocked", last_error="backend unavailable"))
    text = render_progress(report)
    assert "ERROR     = backend unavailable" in text
    assert "RESULT    = NEEDS_ATTENTION" in text
    with pytest.raises(ValueError, match="width"):
        render_progress(report, width=4)
