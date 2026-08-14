from __future__ import annotations

import os
import time
from pathlib import Path

from ai_lab_os.storage_curator import StorageDisposition, build_storage_plan, classify_file


def _old(path: Path, days: int) -> None:
    timestamp = time.time() - days * 86400
    os.utime(path, (timestamp, timestamp))


def test_model_weight_is_review_not_cleanup(tmp_path: Path) -> None:
    path = tmp_path / "model.safetensors"
    path.write_bytes(b"model")
    assert classify_file(path).disposition is StorageDisposition.REVIEW


def test_old_temp_is_cleanup_candidate(tmp_path: Path) -> None:
    path = tmp_path / "old.tmp"
    path.write_bytes(b"x")
    _old(path, 45)
    assert classify_file(path).disposition is StorageDisposition.CLEAN_CANDIDATE


def test_old_archive_is_archive_candidate(tmp_path: Path) -> None:
    path = tmp_path / "backup.zip"
    path.write_bytes(b"x")
    _old(path, 120)
    assert classify_file(path).disposition is StorageDisposition.ARCHIVE


def test_sha256_duplicate_detection_requires_identical_content(tmp_path: Path) -> None:
    payload = b"same-content" * 1024
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    third = tmp_path / "c.bin"
    first.write_bytes(payload)
    second.write_bytes(payload)
    third.write_bytes(b"different!!!" * 1024)
    plan = build_storage_plan((tmp_path,), max_files=100, duplicate_min_bytes=1)
    assert len(plan.duplicates) == 1
    assert set(plan.duplicates[0].paths) == {str(first), str(second)}
    assert plan.duplicates[0].reclaimable_bytes == len(payload)


def test_plan_is_analysis_only_and_does_not_delete_files(tmp_path: Path) -> None:
    path = tmp_path / "old.log"
    path.write_text("keep until approved")
    _old(path, 60)
    plan = build_storage_plan((tmp_path,), max_files=100, duplicate_min_bytes=1)
    assert path.exists()
    assert any(c.path == str(path) and c.disposition is StorageDisposition.CLEAN_CANDIDATE for c in plan.candidates)
