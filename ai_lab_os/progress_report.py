from __future__ import annotations

from dataclasses import dataclass

from ai_lab_os.goal_query_service import GoalStatusSnapshot
from ai_lab_os.product_runtime import ProductRuntime


@dataclass(frozen=True)
class ProgressReport:
    goal_id: str
    status: str
    progress_percent: int
    completed_tasks: int
    total_tasks: int
    current_task: str | None
    recovery_count: int
    recovering: bool
    last_event: str | None
    last_error: str | None
    final_result: str | None


class ProgressReportService:
    """Translate durable runtime state into a compact user-facing report."""

    def __init__(self, runtime: ProductRuntime) -> None:
        self._runtime = runtime

    def get(self, goal_id: str) -> ProgressReport:
        return self.from_snapshot(self._runtime.get_goal(goal_id))

    @staticmethod
    def from_snapshot(snapshot: GoalStatusSnapshot) -> ProgressReport:
        recovery_events = tuple(
            event
            for event in snapshot.events
            if event.startswith(("RESUME:", "RETRY:", "REPAIR:", "REPLAN:"))
        )
        current_task = snapshot.resume_cursor
        if current_task is None:
            running = next((task.task_id for task in snapshot.tasks if task.status == "running"), None)
            current_task = running

        final_result: str | None = None
        if snapshot.status == "complete":
            final_result = "GOAL_COMPLETE"
        elif snapshot.status == "cancelled":
            final_result = "CANCELLED"
        elif snapshot.status == "approval_required":
            final_result = "APPROVAL_REQUIRED"
        elif snapshot.status in {"blocked", "replan_required"}:
            final_result = "NEEDS_ATTENTION"

        recovering = snapshot.status not in {"complete", "cancelled", "paused", "approval_required"} and bool(recovery_events)
        return ProgressReport(
            goal_id=snapshot.goal_id,
            status=snapshot.status,
            progress_percent=snapshot.progress_percent,
            completed_tasks=snapshot.completed_tasks,
            total_tasks=snapshot.total_tasks,
            current_task=current_task,
            recovery_count=len(recovery_events),
            recovering=recovering,
            last_event=snapshot.events[-1] if snapshot.events else None,
            last_error=snapshot.last_error,
            final_result=final_result,
        )


def render_progress(report: ProgressReport, *, width: int = 20) -> str:
    """Render a stable terminal-friendly progress view without clearing the screen."""

    if width < 5:
        raise ValueError("width must be >= 5")
    filled = min(width, max(0, int(report.progress_percent * width / 100)))
    bar = "#" * filled + "-" * (width - filled)
    current = report.current_task or ("complete" if report.status == "complete" else "-")
    recovery = f"{report.recovery_count}" + (" (active)" if report.recovering else "")
    lines = [
        f"GOAL      = {report.goal_id}",
        f"STATUS    = {report.status}",
        f"PROGRESS  = [{bar}] {report.progress_percent}%",
        f"TASKS     = {report.completed_tasks}/{report.total_tasks}",
        f"CURRENT   = {current}",
        f"RECOVERY  = {recovery}",
    ]
    if report.last_error:
        lines.append(f"ERROR     = {report.last_error}")
    if report.final_result:
        lines.append(f"RESULT    = {report.final_result}")
    return "\n".join(lines)
