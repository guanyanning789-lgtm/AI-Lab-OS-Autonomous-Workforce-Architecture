from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class PublishResult:
    committed: bool
    pushed: bool
    branch: str
    commit_sha: str | None = None
    message: str = ""


def _run(
    command: list[str],
    *,
    cwd: Path,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


def publish_result_file(
    result_path: str | Path,
    *,
    runner: Runner = subprocess.run,
    push: bool = True,
) -> PublishResult:
    """Commit exactly one result file and optionally push the current branch.

    Safety properties:
    - never uses shell=True
    - stages only the requested result file
    - never force-pushes
    - never switches branches
    - never stages target-repository code changes
    """
    result_file = Path(result_path).resolve()
    if not result_file.is_file():
        raise FileNotFoundError(result_file)

    repo_probe = _run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=result_file.parent,
        runner=runner,
    )
    if repo_probe.returncode != 0:
        raise RuntimeError("result file is not inside a Git repository")

    repo_root = Path(repo_probe.stdout.strip()).resolve()
    try:
        relative = result_file.relative_to(repo_root)
    except ValueError as exc:
        raise RuntimeError("result file is outside the Git repository") from exc

    if not relative.as_posix().startswith("results/"):
        raise ValueError("only files under results/ may be published")

    branch_probe = _run(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
        runner=runner,
    )
    branch = branch_probe.stdout.strip()
    if branch_probe.returncode != 0 or not branch:
        raise RuntimeError("cannot publish from a detached or unknown branch")

    add = _run(
        ["git", "add", "--", relative.as_posix()],
        cwd=repo_root,
        runner=runner,
    )
    if add.returncode != 0:
        raise RuntimeError(add.stderr.strip() or "git add failed")

    diff = _run(
        ["git", "diff", "--cached", "--quiet", "--", relative.as_posix()],
        cwd=repo_root,
        runner=runner,
    )
    if diff.returncode == 0:
        return PublishResult(
            committed=False,
            pushed=False,
            branch=branch,
            message="result file has no new changes to publish",
        )
    if diff.returncode != 1:
        raise RuntimeError(diff.stderr.strip() or "git diff failed")

    commit = _run(
        [
            "git",
            "commit",
            "-m",
            f"result: publish {result_file.stem}",
            "--",
            relative.as_posix(),
        ],
        cwd=repo_root,
        runner=runner,
    )
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr.strip() or commit.stdout.strip() or "git commit failed")

    sha_probe = _run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        runner=runner,
    )
    commit_sha = sha_probe.stdout.strip() if sha_probe.returncode == 0 else None

    if not push:
        return PublishResult(
            committed=True,
            pushed=False,
            branch=branch,
            commit_sha=commit_sha,
            message="result committed locally",
        )

    push_result = _run(
        ["git", "push", "origin", branch],
        cwd=repo_root,
        runner=runner,
    )
    if push_result.returncode != 0:
        raise RuntimeError(
            push_result.stderr.strip()
            or push_result.stdout.strip()
            or "git push failed"
        )

    return PublishResult(
        committed=True,
        pushed=True,
        branch=branch,
        commit_sha=commit_sha,
        message="result committed and pushed",
    )
