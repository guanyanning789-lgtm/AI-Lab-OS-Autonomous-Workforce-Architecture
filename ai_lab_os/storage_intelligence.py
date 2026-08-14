from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_curator import FileCandidate, StorageDisposition


_PROJECT_MARKERS = {".git", "node_modules", ".venv", "venv", "site-packages", "__pycache__"}
_VERSION_RE = re.compile(r"^(?P<family>.+?)[-_ ]v?(?P<version>\d+(?:\.\d+){0,3})(?P<suffix>[^/]*)$", re.IGNORECASE)
_COPY_SUFFIX_RE = re.compile(r"\s*\((?P<copy>\d+)\)$")


@dataclass(frozen=True)
class ProjectBoundaryResult:
    protected: bool
    boundary: str | None
    reason: str


@dataclass(frozen=True)
class VersionedFile:
    path: str
    family: str
    version: tuple[int, ...]
    raw_version: str


@dataclass(frozen=True)
class VersionFamily:
    family: str
    members: tuple[VersionedFile, ...]
    latest: VersionedFile
    historical: tuple[VersionedFile, ...]


def detect_project_boundary(path: Path) -> ProjectBoundaryResult:
    lowered = [part.lower() for part in path.parts]
    for index, part in enumerate(lowered):
        if part in _PROJECT_MARKERS:
            boundary_parts = path.parts[: index + 1]
            return ProjectBoundaryResult(True, str(Path(*boundary_parts)), f"inside protected project/dependency boundary: {part}")
    return ProjectBoundaryResult(False, None, "not inside known project/dependency boundary")


def apply_project_boundaries(candidates: tuple[FileCandidate, ...]) -> tuple[FileCandidate, ...]:
    output: list[FileCandidate] = []
    for candidate in candidates:
        boundary = detect_project_boundary(Path(candidate.path))
        if boundary.protected:
            output.append(FileCandidate(candidate.path, candidate.size, candidate.age_days, StorageDisposition.PROTECTED, boundary.reason, candidate.sha256))
        else:
            output.append(candidate)
    return tuple(output)


def _versioned(path: Path) -> VersionedFile | None:
    stem = path.stem
    stem = _COPY_SUFFIX_RE.sub("", stem)
    match = _VERSION_RE.match(stem)
    if not match:
        return None
    raw = match.group("version")
    version = tuple(int(part) for part in raw.split("."))
    family = match.group("family").strip("- _").lower()
    if not family:
        return None
    return VersionedFile(str(path), family, version, raw)


def build_version_families(candidates: tuple[FileCandidate, ...]) -> tuple[VersionFamily, ...]:
    grouped: dict[str, list[VersionedFile]] = {}
    for candidate in candidates:
        path = Path(candidate.path)
        if path.suffix.lower() not in {".zip", ".7z", ".rar"}:
            continue
        item = _versioned(path)
        if item is None:
            continue
        grouped.setdefault(item.family, []).append(item)

    families: list[VersionFamily] = []
    for family, members in grouped.items():
        if len(members) < 2:
            continue
        ordered = tuple(sorted(members, key=lambda item: (item.version, item.path)))
        latest = ordered[-1]
        families.append(VersionFamily(family, ordered, latest, ordered[:-1]))
    return tuple(sorted(families, key=lambda item: item.family))
