from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction
from ai_lab_os.storage_executor import StorageExecutionResult
from ai_lab_os.storage_verifier import verify_batch, verify_execution


def test_verified_quarantine_requires_source_absent_and_target_present(tmp_path: Path) -> None:
    target = tmp_path / "q" / "old.tmp"
    target.parent.mkdir()
    target.write_bytes(b"data")
    result = StorageExecutionResult(True, CleanupAction.CLEAN, str(tmp_path / "old.tmp"), None, str(target), "done")
    verified = verify_execution(result)
    assert verified.ok is True
    assert verified.source_absent is True
    assert verified.target_present is True
    assert verified.hash_verified is True


def test_verification_fails_if_source_still_exists(tmp_path: Path) -> None:
    source = tmp_path / "old.tmp"
    target = tmp_path / "q" / "old.tmp"
    source.write_bytes(b"data")
    target.parent.mkdir()
    target.write_bytes(b"data")
    result = StorageExecutionResult(True, CleanupAction.CLEAN, str(source), None, str(target), "done")
    assert verify_execution(result).ok is False


def test_batch_forbids_goal_complete_if_any_action_fails(tmp_path: Path) -> None:
    good = tmp_path / "good.mp4"
    good.parent.mkdir(exist_ok=True)
    good.write_bytes(b"good")
    first = StorageExecutionResult(True, CleanupAction.MIGRATE, str(tmp_path / "old-good.mp4"), str(good), None, "done")
    second = StorageExecutionResult(False, CleanupAction.MIGRATE, str(tmp_path / "old-bad.mp4"), str(tmp_path / "missing.mp4"), None, "failed")
    batch = verify_batch((first, second))
    assert batch.ok is False
    assert batch.verified == 1
    assert batch.failed == 1
    assert "GOAL_COMPLETE forbidden" in batch.message


def test_empty_batch_cannot_claim_success() -> None:
    batch = verify_batch(())
    assert batch.ok is False
    assert "GOAL_COMPLETE forbidden" in batch.message
