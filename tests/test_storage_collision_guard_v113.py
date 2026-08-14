from pathlib import Path

from ai_lab_os.storage_collision_guard import GuardDecision, guard_migration
from ai_lab_os.storage_path_planner import MigrationProposal, MigrationRisk


def proposal(source: Path, destination: Path | None, risk: MigrationRisk = MigrationRisk.MEDIUM) -> MigrationProposal:
    return MigrationProposal(str(source), None if destination is None else str(destination), "test", risk, True, "test")


def test_missing_destination_path_is_blocked(tmp_path: Path) -> None:
    source = tmp_path / "a.bin"
    source.write_bytes(b"a")
    result = guard_migration(proposal(source, None))
    assert result.decision is GuardDecision.BLOCKED
    assert result.executable is False


def test_identical_destination_becomes_duplicate_not_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "a.bin"
    destination = tmp_path / "b.bin"
    source.write_bytes(b"same")
    destination.write_bytes(b"same")
    result = guard_migration(proposal(source, destination))
    assert result.decision is GuardDecision.SAME_CONTENT
    assert result.executable is False


def test_different_destination_is_collision(tmp_path: Path) -> None:
    source = tmp_path / "a.bin"
    destination = tmp_path / "b.bin"
    source.write_bytes(b"one")
    destination.write_bytes(b"two")
    result = guard_migration(proposal(source, destination))
    assert result.decision is GuardDecision.COLLISION
    assert result.executable is False


def test_code_file_is_reference_risk(tmp_path: Path) -> None:
    source = tmp_path / "tool.py"
    source.write_text("print('x')")
    result = guard_migration(proposal(source, tmp_path / "elsewhere" / "tool.py"))
    assert result.decision is GuardDecision.REFERENCE_RISK
    assert result.executable is False


def test_clean_destination_is_only_safe_to_plan_not_execute(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    result = guard_migration(proposal(source, tmp_path / "media" / "video.mp4"))
    assert result.decision is GuardDecision.SAFE_TO_PLAN
    assert result.executable is False
