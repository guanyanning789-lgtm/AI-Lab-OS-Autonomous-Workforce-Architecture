from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManagedRepository:
    name: str
    path: str
    branch: str
    enabled: bool = True


@dataclass(frozen=True)
class SyncResult:
    name: str
    status: str
    message: str = ""


def load_managed_repositories(path: str | Path) -> tuple[ManagedRepository, ...]:
    config_path = Path(path)
    if not config_path.exists():
        return ()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    items = raw.get("repositories", []) if isinstance(raw, dict) else []
    repositories: list[ManagedRepository] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        repo = ManagedRepository(
            name=str(item.get("name", "")).strip(),
            path=str(item.get("path", "")).strip(),
            branch=str(item.get("branch", "")).strip(),
            enabled=bool(item.get("enabled", True)),
        )
        if repo.name and repo.path and repo.branch:
            repositories.append(repo)
    return tuple(repositories)


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


def sync_repository(repo: ManagedRepository) -> SyncResult:
    if not repo.enabled:
        return SyncResult(repo.name, "disabled")

    repository = Path(repo.path).resolve()
    if not repository.exists() or not repository.is_dir():
        return SyncResult(repo.name, "unavailable", "repository path does not exist")

    branch = _git(["branch", "--show-current"], cwd=repository)
    current = (branch.stdout or "").strip()
    if branch.returncode != 0:
        return SyncResult(repo.name, "error", (branch.stderr or "git branch failed").strip())
    if current != repo.branch:
        return SyncResult(
            repo.name,
            "blocked",
            f"expected branch {repo.branch!r}, found {current!r}",
        )

    status = _git(["status", "--porcelain"], cwd=repository)
    if status.returncode != 0:
        return SyncResult(repo.name, "error", (status.stderr or "git status failed").strip())
    if (status.stdout or "").strip():
        return SyncResult(repo.name, "blocked", "working tree is not clean")

    before = _git(["rev-parse", "HEAD"], cwd=repository)
    if before.returncode != 0:
        return SyncResult(repo.name, "error", (before.stderr or "git rev-parse failed").strip())

    pull = _git(["pull", "--ff-only"], cwd=repository)
    if pull.returncode != 0:
        detail = (pull.stderr or pull.stdout or "git pull failed").strip()
        return SyncResult(repo.name, "error", detail)

    after = _git(["rev-parse", "HEAD"], cwd=repository)
    if after.returncode != 0:
        return SyncResult(repo.name, "error", (after.stderr or "git rev-parse failed").strip())

    changed = (before.stdout or "").strip() != (after.stdout or "").strip()
    return SyncResult(repo.name, "updated" if changed else "current")


def sync_managed_repositories(path: str | Path) -> tuple[SyncResult, ...]:
    return tuple(sync_repository(repo) for repo in load_managed_repositories(path))
