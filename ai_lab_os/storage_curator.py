from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class StorageDisposition(str, Enum):
    PROTECTED = "protected"
    KEEP = "keep"
    ARCHIVE = "archive"
    DUPLICATE = "duplicate"
    CLEAN_CANDIDATE = "clean_candidate"
    REVIEW = "review"


@dataclass(frozen=True)
class FileCandidate:
    path: str
    size: int
    age_days: int
    disposition: StorageDisposition
    reason: str
    sha256: str | None = None


@dataclass(frozen=True)
class DuplicateGroup:
    sha256: str
    size: int
    paths: tuple[str, ...]
    reclaimable_bytes: int


@dataclass(frozen=True)
class StoragePlan:
    candidates: tuple[FileCandidate, ...]
    duplicates: tuple[DuplicateGroup, ...]
    reclaimable_bytes: int
    scanned_files: int
    truncated: bool


_PROTECTED_NAMES = {
    "pagefile.sys", "swapfile.sys", "hiberfil.sys", "ntldr", "bootmgr",
}
_PROTECTED_PARTS = {"windows", "program files", "program files (x86)", ".git"}
_TEMP_SUFFIXES = {".tmp", ".temp", ".log"}
_ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar", ".tar", ".gz"}
_MODEL_SUFFIXES = {".safetensors", ".gguf", ".ckpt", ".pt", ".pth"}


def _age_days(path: Path, now: float) -> int:
    try:
        return max(0, int((now - path.stat().st_mtime) // 86400))
    except OSError:
        return 0


def classify_file(path: Path, *, now: float | None = None) -> FileCandidate:
    now = time.time() if now is None else now
    stat = path.stat()
    lower_parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    suffix = path.suffix.lower()
    age = _age_days(path, now)

    if name in _PROTECTED_NAMES or lower_parts & _PROTECTED_PARTS:
        return FileCandidate(str(path), stat.st_size, age, StorageDisposition.PROTECTED, "system/project protected path")
    if suffix in _MODEL_SUFFIXES:
        return FileCandidate(str(path), stat.st_size, age, StorageDisposition.REVIEW, "AI model weight; never auto-delete")
    if "$recycle.bin" in lower_parts:
        return FileCandidate(str(path), stat.st_size, age, StorageDisposition.CLEAN_CANDIDATE, "Recycle Bin content; approval required before cleanup")
    if suffix in _TEMP_SUFFIXES and age >= 30:
        return FileCandidate(str(path), stat.st_size, age, StorageDisposition.CLEAN_CANDIDATE, "old temporary/log file")
    if suffix in _ARCHIVE_SUFFIXES and age >= 90:
        return FileCandidate(str(path), stat.st_size, age, StorageDisposition.ARCHIVE, "old archive; review or move to Archive")
    return FileCandidate(str(path), stat.st_size, age, StorageDisposition.KEEP, "no safe cleanup rule matched")


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def build_storage_plan(
    roots: tuple[Path, ...],
    *,
    max_files: int = 100_000,
    duplicate_min_bytes: int = 10 * 1024 * 1024,
) -> StoragePlan:
    candidates: list[FileCandidate] = []
    duplicate_sizes: dict[int, list[Path]] = {}
    scanned = 0
    truncated = False

    for root in roots:
        if not root.exists():
            continue
        for current, dirs, files in os.walk(root, topdown=True, onerror=lambda _exc: None):
            dirs[:] = [d for d in dirs if d.lower() not in {"system volume information"}]
            for filename in files:
                if scanned >= max_files:
                    truncated = True
                    break
                path = Path(current) / filename
                try:
                    candidate = classify_file(path)
                except OSError:
                    continue
                candidates.append(candidate)
                scanned += 1
                if candidate.size >= duplicate_min_bytes and candidate.disposition is not StorageDisposition.PROTECTED:
                    duplicate_sizes.setdefault(candidate.size, []).append(path)
            if truncated:
                break
        if truncated:
            break

    groups: list[DuplicateGroup] = []
    for size, paths in duplicate_sizes.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[str]] = {}
        for path in paths:
            try:
                digest = _sha256(path)
            except OSError:
                continue
            by_hash.setdefault(digest, []).append(str(path))
        for digest, matching in by_hash.items():
            if len(matching) >= 2:
                groups.append(DuplicateGroup(digest, size, tuple(matching), size * (len(matching) - 1)))

    duplicate_paths = {path for group in groups for path in group.paths[1:]}
    enriched = tuple(
        FileCandidate(c.path, c.size, c.age_days, StorageDisposition.DUPLICATE, "SHA256-identical duplicate; keep one copy", next((g.sha256 for g in groups if c.path in g.paths), None))
        if c.path in duplicate_paths else c
        for c in candidates
    )
    reclaimable = sum(g.reclaimable_bytes for g in groups) + sum(
        c.size for c in enriched if c.disposition is StorageDisposition.CLEAN_CANDIDATE
    )
    return StoragePlan(enriched, tuple(sorted(groups, key=lambda g: g.reclaimable_bytes, reverse=True)), reclaimable, scanned, truncated)
