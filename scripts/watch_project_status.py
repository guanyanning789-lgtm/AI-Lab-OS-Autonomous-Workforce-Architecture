from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_BRANCH = "ai/v0.3-supervisor-runtime"
STATUS_PATH = "status/project_status.json"
BAR_WIDTH = 34
ANIMATION_FRAMES = ("▏", "▎", "▍", "▌", "▋", "▊", "▉", "█", "▉", "▊", "▋", "▌", "▍", "▎")


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


def _percent(payload: dict[str, object]) -> int:
    raw = payload.get("percent", 0)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0
    return max(0, min(100, value))


def _progress_bar(percent: int, frame_index: int) -> str:
    filled = int(BAR_WIDTH * percent / 100)
    empty = BAR_WIDTH - filled
    base = "█" * filled + "·" * empty

    if 0 < percent < 100 and filled < BAR_WIDTH:
        cursor = min(BAR_WIDTH - 1, filled)
        chars = list(base)
        chars[cursor] = ANIMATION_FRAMES[frame_index % len(ANIMATION_FRAMES)]
        base = "".join(chars)

    return f"[{base}] {percent:3d}%"


def _screen(payload: dict[str, object], frame_index: int, branch: str, seconds_until_sync: float) -> str:
    percent = _percent(payload)
    lines = [
        "=" * 78,
        "                         AI LAB OS LIVE PROGRESS",
        "=" * 78,
        f"BRANCH      = {branch}",
        f"MILESTONE   = {payload.get('milestone', 'unknown')}",
        "",
        f"PROGRESS    {_progress_bar(percent, frame_index)}",
        f"STATUS      = {payload.get('progress', 'unknown')}",
        "",
        f"NOW         = {payload.get('current_work', 'not specified')}",
        "",
        f"NEXT        = {payload.get('next_step', 'not specified')}",
        "",
        f"USER ACTION = {payload.get('user_action', 'None')}",
        "",
        f"REMOTE SYNC = {max(0.0, seconds_until_sync):4.1f}s   |   Ctrl+C to stop",
        "=" * 78,
    ]
    return "\n".join(lines)


def _clear_screen() -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="", flush=True)
    else:
        print("\n" * 2, end="", flush=True)


def watch(repository: Path, branch: str, poll_seconds: float) -> None:
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be > 0")

    payload: dict[str, object] = {
        "milestone": "Connecting to GitHub...",
        "progress": "Waiting for first remote sync",
        "percent": 0,
        "current_work": "Fetching project status",
        "next_step": "Remote status will appear automatically",
        "user_action": "None",
    }
    last_sync = 0.0
    frame = 0
    last_error: str | None = None

    while True:
        now = time.monotonic()
        if now - last_sync >= poll_seconds or last_sync == 0.0:
            try:
                payload = _fetch_status(repository, branch)
                last_error = None
            except Exception as exc:
                last_error = str(exc)
            last_sync = now

        shown = dict(payload)
        if last_error:
            shown["current_work"] = f"Remote sync error: {last_error}"
            shown["user_action"] = "Watcher will retry automatically"

        elapsed = time.monotonic() - last_sync
        remaining = poll_seconds - elapsed
        _clear_screen()
        print(_screen(shown, frame, branch, remaining), flush=True)
        frame += 1
        time.sleep(0.10)


def main() -> int:
    parser = argparse.ArgumentParser(description="Animated read-only AI Lab OS remote development progress watcher")
    parser.add_argument("--repo", default=".", help="local clone of the AI Lab OS repository")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    args = parser.parse_args()

    repository = Path(args.repo).resolve()
    if not (repository / ".git").exists():
        raise SystemExit(f"Not a git repository: {repository}")

    try:
        watch(repository, args.branch, args.poll_seconds)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
