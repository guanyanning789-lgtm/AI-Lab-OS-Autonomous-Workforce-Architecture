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

# A project can be real even when it has no Git/config marker at its root.
# Require several project-shaped child directories so ordinary folders such as
# Desktop/Downloads are not promoted to project roots accidentally.
_COMPOSITE_PROJECT_DIRS = {
    "src",
    "tests",
    "scripts",
    "dataset",
    "datasets",
    "workflows",
    "output",
    "outputs",
    "models",
    "checkpoints",
    "configs",
    "config",
    "prompts",
    "toolkit",
    "tools",
    "app",
    "apps",
    "shot_factory",
}
_COMPOSITE_MIN_MATCHES = 3


@dataclass(frozen=True)
class ProjectRoot:
    path: str
    marker: str


def _composite_marker(directory: Path) -> str | None:
    try:
        child_dirs = {child.name.lower() for child in directory.iterdir() if child.is_dir()}
    except OSError:
        return None
    matches = sorted(child_dirs & _COMPOSITE_PROJECT_DIRS)
    if len(matches) < _COMPOSITE_MIN_MATCHES:
        return None
    return "composite:" + ",".join(matches)


def detect_project_roots(candidates: tuple[FileCandidate, ...]) -> tuple[ProjectRoot, ...]:
    candidate_paths = [Path(item.path) for item in candidates]
    directories: set[Path] = set()
    for path in candidate_paths:
        parent = path.parent
        for ancestor in (parent, *parent.parents):
            directories.add(ancestor)

    discovered: list[ProjectRoot] = []
    for directory in sorted(directories, key=lambda p: len(p.parts)):
        marker = next((name for name in _PROJECT_ROOT_MARKERS if (directory / name).exists()), None)
        marker = marker or _composite_marker(directory)
        if marker is None:
            continue
        discovered.append(ProjectRoot(str(directory), marker))

    # Prefer the highest meaningful root. Once a parent project is detected,
    # nested tool repos/environments are already protected by that parent.
    roots: list[ProjectRoot] = []
    for candidate in sorted(discovered, key=lambda root: len(Path(root.path).parts)):
        directory = Path(candidate.path)
        if any(Path(existing.path) in directory.parents or directory == Path(existing.path) for existing in roots):
            continue
        roots.append(candidate)
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
