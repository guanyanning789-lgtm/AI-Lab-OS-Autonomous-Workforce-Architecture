from pathlib import Path

from ai_lab_os.storage_curator import FileCandidate, StorageDisposition
from ai_lab_os.storage_path_planner import MigrationRisk, propose_path


def candidate(path: str, disposition: StorageDisposition = StorageDisposition.KEEP) -> FileCandidate:
    return FileCandidate(path, 100, 10, disposition, "test")


def test_model_gets_canonical_model_destination_but_requires_approval() -> None:
    result = propose_path(candidate(r"C:\Users\PC\Downloads\flux.safetensors", StorageDisposition.REVIEW))
    assert result.destination == r"D:\AI-Lab\Models\flux.safetensors"
    assert result.category == "AI Models"
    assert result.risk is MigrationRisk.HIGH
    assert result.approval_required is True


def test_video_gets_media_destination_and_requires_approval() -> None:
    result = propose_path(candidate(r"C:\Users\PC\Downloads\clip.mp4"))
    assert result.destination == r"D:\AI-Lab\Media\Video\clip.mp4"
    assert result.approval_required is True


def test_protected_file_is_blocked() -> None:
    result = propose_path(candidate(r"C:\pagefile.sys", StorageDisposition.PROTECTED))
    assert result.destination is None
    assert result.risk is MigrationRisk.BLOCKED
    assert result.approval_required is False


def test_unknown_type_never_gets_invented_destination() -> None:
    result = propose_path(candidate(r"C:\Users\PC\Downloads\mystery.xyz"))
    assert result.destination is None
    assert result.risk is MigrationRisk.MEDIUM
    assert result.approval_required is True
