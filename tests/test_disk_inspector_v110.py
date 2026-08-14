from __future__ import annotations

from pathlib import Path

from ai_lab_os.disk_inspector import (
    DiskInspectionReport,
    DiskInspectorExecutor,
    DiskItem,
    DriveSummary,
    render_disk_report,
)
from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind


class _FakeInspector:
    def __init__(self, report: DiskInspectionReport) -> None:
        self.report = report

    def inspect(self) -> DiskInspectionReport:
        return self.report


def _task() -> PlannedTask:
    return PlannedTask(
        task_id="disk-1",
        goal_id="goal-1",
        sequence=1,
        kind=PlannedTaskKind.VERIFY,
        description="Inspect disks read only.",
        agent=AgentKind.COMPUTER,
    )


def test_disk_executor_requires_real_capacity_evidence() -> None:
    empty = DiskInspectorExecutor(_FakeInspector(DiskInspectionReport(())))
    result = empty(_task())
    assert result.status is TaskExecutionStatus.FAILED
    assert "no capacity evidence" in result.message


def test_disk_executor_completes_when_evidence_exists() -> None:
    report = DiskInspectionReport((
        DriveSummary(
            drive="C:\\",
            total_bytes=1000,
            used_bytes=600,
            free_bytes=400,
            scanned_entries=2,
            truncated=False,
            inaccessible_entries=0,
            largest_directories=(DiskItem("C:\\Users", 300),),
            largest_files=(DiskItem("C:\\big.bin", 200),),
        ),
    ))
    executor = DiskInspectorExecutor(_FakeInspector(report))
    result = executor(_task())
    assert result.status is TaskExecutionStatus.SUCCESS
    assert executor.last_report == report


def test_disk_report_labels_partial_observed_rankings() -> None:
    report = DiskInspectionReport((
        DriveSummary(
            drive="C:\\",
            total_bytes=1024**3,
            used_bytes=512 * 1024**2,
            free_bytes=512 * 1024**2,
            scanned_entries=50_000,
            truncated=True,
            inaccessible_entries=3,
            largest_directories=(DiskItem("C:\\Users", 128 * 1024**2),),
            largest_files=(DiskItem("C:\\Users\\x.bin", 64 * 1024**2),),
        ),
    ))
    text = render_disk_report(report)
    assert "READ ONLY" in text
    assert "SCAN = PARTIAL" in text
    assert "LARGEST DIRECTORIES (observed)" in text
    assert "C:\\Users" in text
