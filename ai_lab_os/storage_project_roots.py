from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_curator import FileCandidate, StorageDisposition


_PROJECT_ROOT_MARKERS = (
    ".git",
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "environment.yml",
    "environment.yaml",
    "setup.py",
)


@dataclass(frozen=True)
class ProjectRoot:
    path: str
    marker: str


def detect_project_roots(candidates: tuple[FileCandidate, ...]) -> tuple[ProjectRoot, ...]:
    candidate_paths = [Path(item.path) for item in candidates]
    directories: set[Path] = set()
    for path in candidate_paths:
        parent = path.parent
        for ancestor in (parent, *parent.parents):
            directories.add(ancestor)

    roots: list[ProjectRoot] = []
    for directory in sorted(directories, key=lambda p: len(p.parts)):
        marker = next((name for name in _PROJECT_ROOT_MARKERS if (directory / name).exists()), None)
        if marker is None:
            continue
        if any(directory == Path(root.path) or Path(root.path) in directory.parents for root in roots):
            continue
        roots.append(ProjectRoot(str(directory), marker))
    return tuple(roots)


def apply_project_root_protection(
    candidates: tuple[FileCandidate, ...],
    roots: tuple[ProjectRoot, ...],
) -> tuple[FileCandidate, ...]:
    root_paths = tuple(Path(root.path) for root in roots)
    output: list[FileCandidate] = []
    for candidate in candidates:
        path = Path(candidate.path)
        matched = next((root for root in root_paths if path == root or root in path.parents), None)
        if matched is None:
            output.append(candidate)
            continue
        output.append(
            FileCandidate(
                candidate.path,
                candidate.size,
                candidate.age_days,
                StorageDisposition.PROTECTED,
                f"inside detected project root: {matched}",
                candidate.sha256,
            )
        )
    return tuple(output)
