from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction
from ai_lab_os.storage_executor import StorageExecutionResult


@dataclass(frozen=True)
class StorageVerificationResult:
    ok: bool
    action: CleanupAction
    source_absent: bool
    target_present: bool
    hash_verified: bool
    message: str


@dataclass(frozen=True)
class StorageBatchVerification:
    ok: bool
    verified: int
    failed: int
    results: tuple[StorageVerificationResult, ...]
    message: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_execution(result: StorageExecutionResult, *, expected_sha256: str | None = None) -> StorageVerificationResult:
    source = Path(result.source)
    source_absent = not source.exists()

    target_text = result.quarantine_path or result.destination
    target = Path(target_text) if target_text else None
    target_present = bool(target and target.exists() and target.is_file())

    hash_verified = False
    if target_present:
        try:
            actual = _sha256(target)  # type: ignore[arg-type]
            hash_verified = expected_sha256 is None or actual == expected_sha256
        except OSError:
            hash_verified = False

    ok = bool(result.ok and source_absent and target_present and hash_verified)
    return StorageVerificationResult(
        ok=ok,
        action=result.action,
        source_absent=source_absent,
        target_present=target_present,
        hash_verified=hash_verified,
        message="verified" if ok else "post-action verification failed; do not declare GOAL_COMPLETE",
    )


def verify_batch(results: tuple[StorageExecutionResult, ...]) -> StorageBatchVerification:
    verified = tuple(verify_execution(item) for item in results)
    failures = sum(1 for item in verified if not item.ok)
    return StorageBatchVerification(
        ok=bool(verified) and failures == 0,
        verified=sum(1 for item in verified if item.ok),
        failed=failures,
        results=verified,
        message=("all approved storage actions verified; GOAL_COMPLETE allowed" if verified and failures == 0 else "verification incomplete or failed; GOAL_COMPLETE forbidden"),
    )
