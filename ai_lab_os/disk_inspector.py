from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask


@dataclass(frozen=True)
class DiskItem:
    path: str
    size_bytes: int


@dataclass(frozen=True)
class DriveSummary:
    drive: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    scanned_entries: int
    truncated: bool
    inaccessible_entries: int
    largest_directories: tuple[DiskItem, ...]
    largest_files: tuple[DiskItem, ...]


@dataclass(frozen=True)
class DiskInspectionReport:
    drives: tuple[DriveSummary, ...]

    @property
    def has_evidence(self) -> bool:
        return bool(self.drives) and all(item.total_bytes > 0 for item in self.drives)


class DiskInspector:
    """Bounded, read-only Windows disk scanner.

    It never deletes, moves, renames, opens for writing, or mutates files. Capacity
    values are exact. Directory/file rankings are based on the entries actually
    scanned and are marked truncated when the safety bound is reached.
    """

    def __init__(self, *, max_entries_per_drive: int = 50_000, top_n: int = 10) -> None:
        if max_entries_per_drive < 1:
            raise ValueError("max_entries_per_drive must be >= 1")
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        self.max_entries_per_drive = max_entries_per_drive
        self.top_n = top_n

    @staticmethod
    def _windows_drives() -> tuple[Path, ...]:
        if os.name == "nt":
            drives = tuple(Path(f"{letter}:\\") for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{letter}:\\").exists())
            return drives
        root = Path("/")
        return (root,) if root.exists() else ()

    def inspect(self) -> DiskInspectionReport:
        return DiskInspectionReport(tuple(self._inspect_drive(drive) for drive in self._windows_drives()))

    def _inspect_drive(self, drive: Path) -> DriveSummary:
        usage = shutil.disk_usage(drive)
        scanned = 0
        inaccessible = 0
        truncated = False
        directory_sizes: dict[str, int] = {}
        largest_files: list[DiskItem] = []

        try:
            root_children = {str(child): child.name for child in drive.iterdir()}
        except OSError:
            root_children = {}
            inaccessible += 1

        for root, dirs, files in os.walk(drive, topdown=True, onerror=lambda _exc: None):
            # Skip common pseudo/reparse loops where possible; permission failures
            # are tolerated and reported rather than causing a write or elevation.
            dirs[:] = [name for name in dirs if name not in {"$RECYCLE.BIN", "System Volume Information"}]
            for name in files:
                if scanned >= self.max_entries_per_drive:
                    truncated = True
                    dirs[:] = []
                    break
                path = Path(root) / name
                scanned += 1
                try:
                    size = path.stat().st_size
                except OSError:
                    inaccessible += 1
                    continue

                try:
                    relative = path.relative_to(drive)
                    first = relative.parts[0] if relative.parts else path.name
                except ValueError:
                    first = path.name
                top_path = str(drive / first)
                directory_sizes[top_path] = directory_sizes.get(top_path, 0) + size
                largest_files.append(DiskItem(str(path), size))
                if len(largest_files) > self.top_n * 4:
                    largest_files.sort(key=lambda item: item.size_bytes, reverse=True)
                    del largest_files[self.top_n :]
            if truncated:
                break

        top_dirs = tuple(
            DiskItem(path, size)
            for path, size in sorted(directory_sizes.items(), key=lambda item: item[1], reverse=True)[: self.top_n]
        )
        top_files = tuple(sorted(largest_files, key=lambda item: item.size_bytes, reverse=True)[: self.top_n])
        return DriveSummary(
            drive=str(drive),
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            scanned_entries=scanned,
            truncated=truncated,
            inaccessible_entries=inaccessible,
            largest_directories=top_dirs,
            largest_files=top_files,
        )


class DiskInspectorExecutor:
    """Supervisor executor that can only complete after real disk evidence exists."""

    def __init__(self, inspector: DiskInspector | None = None) -> None:
        self.inspector = inspector or DiskInspector()
        self.last_report: DiskInspectionReport | None = None

    def __call__(self, task: PlannedTask) -> TaskExecutionResult:
        if task.agent is not AgentKind.COMPUTER:
            return TaskExecutionResult(TaskExecutionStatus.FAILED, "DiskInspector refuses non-computer task")
        try:
            report = self.inspector.inspect()
        except Exception as exc:
            return TaskExecutionResult(TaskExecutionStatus.FAILED, f"disk inspection failed: {exc}")
        self.last_report = report
        if not report.has_evidence:
            return TaskExecutionResult(TaskExecutionStatus.FAILED, "disk inspection produced no capacity evidence")
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, f"disk evidence collected for {len(report.drives)} drive(s)")


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if amount < 1024.0 or unit == "PB":
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    return f"{amount:.1f} PB"


def render_disk_report(report: DiskInspectionReport) -> str:
    lines = ["DISK INSPECTOR (READ ONLY)"]
    for drive in report.drives:
        scan_state = "PARTIAL" if drive.truncated else "COMPLETE"
        lines.extend([
            "",
            f"DRIVE = {drive.drive}",
            f"CAPACITY = {format_bytes(drive.total_bytes)}",
            f"USED = {format_bytes(drive.used_bytes)}",
            f"FREE = {format_bytes(drive.free_bytes)}",
            f"SCAN = {scan_state}; files={drive.scanned_entries}; inaccessible={drive.inaccessible_entries}",
            "LARGEST DIRECTORIES (observed):",
        ])
        lines.extend(f"  {format_bytes(item.size_bytes):>10}  {item.path}" for item in drive.largest_directories)
        lines.append("LARGEST FILES (observed):")
        lines.extend(f"  {format_bytes(item.size_bytes):>10}  {item.path}" for item in drive.largest_files)
    return "\n".join(lines)
