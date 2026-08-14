from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


DEFAULT_BRANCH = "ai/v0.3-supervisor-runtime"
STATUS_PATH = "status/project_status.json"


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


def _fetch_status(repository: Path, branch: str) -> dict[str, object]:
    fetch = _git(["fetch", "origin", branch], cwd=repository)
    if fetch.returncode != 0:
        raise RuntimeError((fetch.stderr or fetch.stdout or "git fetch failed").strip())

    show = _git(["show", f"origin/{branch}:{STATUS_PATH}"], cwd=repository)
    if show.returncode != 0:
        raise RuntimeError((show.stderr or show.stdout or "git show failed").strip())

    payload = json.loads(show.stdout)
    if not isinstance(payload, dict):
        raise ValueError("project status must be a JSON object")
    return payload


def _render(payload: dict[str, object]) -> str:
    lines = [
        "=" * 72,
        "AI LAB OS LIVE DEVELOPMENT STATUS",
        f"MILESTONE   = {payload.get('milestone', 'unknown')}",
        f"PROGRESS    = {payload.get('progress', 'unknown')}",
        f"NOW         = {payload.get('current_work', 'not specified')}",
        f"NEXT        = {payload.get('next_step', 'not specified')}",
        f"FINISH LINE = {payload.get('finish_line', 'not specified')}",
        f"USER ACTION = {payload.get('user_action', 'None')}",
        "=" * 72,
    ]
    return "\n".join(lines)


def watch(repository: Path, branch: str, poll_seconds: float) -> None:
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be > 0")

    last_fingerprint: str | None = None
    print(f"WATCHING = origin/{branch}", flush=True)
    print("MODE = read-only remote status; local working tree is not modified", flush=True)

    while True:
        try:
            payload = _fetch_status(repository, branch)
            fingerprint = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if fingerprint != last_fingerprint:
                print("", flush=True)
                print(_render(payload), flush=True)
                last_fingerprint = fingerprint
        except Exception as exc:
            print(f"STATUS WATCH ERROR = {exc}", flush=True)
        time.sleep(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch AI Lab OS project status from the remote branch without changing local files")
    parser.add_argument("--repo", default=".", help="local clone of the AI Lab OS repository")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    args = parser.parse_args()

    repository = Path(args.repo).resolve()
    if not (repository / ".git").exists():
        raise SystemExit(f"Not a git repository: {repository}")

    watch(repository, args.branch, args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
