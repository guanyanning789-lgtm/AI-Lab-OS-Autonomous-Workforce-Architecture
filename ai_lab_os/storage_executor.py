from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction, CleanupItem


@dataclass(frozen=True)
class StorageApproval:
    path: str
    action: CleanupAction
    approved: bool


@dataclass(frozen=True)
class StorageExecutionResult:
    ok: bool
    action: CleanupAction
    source: str
    destination: str | None
    quarantine_path: str | None
    message: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def execute_cleanup_item(
    item: CleanupItem,
    approval: StorageApproval,
    *,
    quarantine_root: Path,
) -> StorageExecutionResult:
    if not item.approval_required:
        return StorageExecutionResult(False, item.action, item.path, item.destination, None, "item is not executable through approval path")
    if not approval.approved or approval.path != item.path or approval.action is not item.action:
        return StorageExecutionResult(False, item.action, item.path, item.destination, None, "explicit matching approval required")

    source = Path(item.path)
    if not source.exists() or not source.is_file():
        return StorageExecutionResult(False, item.action, item.path, item.destination, None, "source file missing or not a regular file")

    if item.action in {CleanupAction.REVIEW, CleanupAction.BLOCK, CleanupAction.KEEP}:
        return StorageExecutionResult(False, item.action, item.path, item.destination, None, "review/protected items cannot be executed")

    if item.action in {CleanupAction.CLEAN, CleanupAction.DELETE_DUPLICATE}:
        quarantine_root.mkdir(parents=True, exist_ok=True)
        destination = quarantine_root / source.name
        counter = 1
        while destination.exists():
            destination = quarantine_root / f"{source.stem}.{counter}{source.suffix}"
            counter += 1
        before_hash = _sha256(source)
        shutil.move(str(source), str(destination))
        if not destination.exists() or _sha256(destination) != before_hash:
            return StorageExecutionResult(False, item.action, item.path, None, str(destination), "quarantine verification failed")
        return StorageExecutionResult(True, item.action, item.path, None, str(destination), "moved to quarantine; no permanent deletion performed")

    if item.action in {CleanupAction.MIGRATE, CleanupAction.ARCHIVE}:
        if not item.destination:
            return StorageExecutionResult(False, item.action, item.path, None, None, "destination required")
        destination = Path(item.destination)
        if destination.exists():
            return StorageExecutionResult(False, item.action, item.path, item.destination, None, "destination exists; overwrite forbidden")
        destination.parent.mkdir(parents=True, exist_ok=True)
        before_hash = _sha256(source)
        shutil.move(str(source), str(destination))
        if not destination.exists() or _sha256(destination) != before_hash:
            return StorageExecutionResult(False, item.action, item.path, item.destination, None, "post-move hash verification failed")
        return StorageExecutionResult(True, item.action, item.path, item.destination, None, "move completed and SHA256 verified")

    return StorageExecutionResult(False, item.action, item.path, item.destination, None, "unsupported cleanup action")
