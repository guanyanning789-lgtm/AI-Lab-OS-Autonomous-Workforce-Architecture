from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction, CleanupItem
from ai_lab_os.storage_executor import StorageApproval, execute_cleanup_item


def item(path: Path, action: CleanupAction, destination: Path | None = None) -> CleanupItem:
    return CleanupItem(str(path), action, path.stat().st_size, True, "test", None if destination is None else str(destination))


def test_execution_requires_exact_explicit_approval(tmp_path: Path) -> None:
    source = tmp_path / "old.tmp"
    source.write_bytes(b"data")
    result = execute_cleanup_item(item(source, CleanupAction.CLEAN), StorageApproval(str(source), CleanupAction.CLEAN, False), quarantine_root=tmp_path / "q")
    assert result.ok is False
    assert source.exists()


def test_clean_moves_to_quarantine_not_permanent_delete(tmp_path: Path) -> None:
    source = tmp_path / "old.tmp"
    source.write_bytes(b"data")
    result = execute_cleanup_item(item(source, CleanupAction.CLEAN), StorageApproval(str(source), CleanupAction.CLEAN, True), quarantine_root=tmp_path / "q")
    assert result.ok is True
    assert not source.exists()
    assert Path(result.quarantine_path).read_bytes() == b"data"
    assert "no permanent deletion" in result.message


def test_migration_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    destination = tmp_path / "media" / "video.mp4"
    source.write_bytes(b"source")
    destination.parent.mkdir()
    destination.write_bytes(b"existing")
    result = execute_cleanup_item(item(source, CleanupAction.MIGRATE, destination), StorageApproval(str(source), CleanupAction.MIGRATE, True), quarantine_root=tmp_path / "q")
    assert result.ok is False
    assert source.exists()
    assert destination.read_bytes() == b"existing"


def test_migration_moves_and_verifies_hash(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    destination = tmp_path / "media" / "video.mp4"
    source.write_bytes(b"video-bytes")
    result = execute_cleanup_item(item(source, CleanupAction.MIGRATE, destination), StorageApproval(str(source), CleanupAction.MIGRATE, True), quarantine_root=tmp_path / "q")
    assert result.ok is True
    assert not source.exists()
    assert destination.read_bytes() == b"video-bytes"
    assert "SHA256 verified" in result.message


def test_review_item_can_never_execute_even_with_approval(tmp_path: Path) -> None:
    source = tmp_path / "model.gguf"
    source.write_bytes(b"model")
    result = execute_cleanup_item(item(source, CleanupAction.REVIEW), StorageApproval(str(source), CleanupAction.REVIEW, True), quarantine_root=tmp_path / "q")
    assert result.ok is False
    assert source.exists()
