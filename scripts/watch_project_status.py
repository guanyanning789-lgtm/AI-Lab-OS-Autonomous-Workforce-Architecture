from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_BRANCH = "ai/v0.3-supervisor-runtime"
STATUS_PATH = "status/project_status.json"
BAR_WIDTH = 46
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


def _clamped_int(raw: object) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0
    return max(0, min(100, value))


def _progress_bar(percent: int, frame_index: int, *, animate: bool) -> str:
    filled = int(BAR_WIDTH * percent / 100)
    empty = BAR_WIDTH - filled
    chars = list("█" * filled + "·" * empty)

    if animate and percent < 100 and BAR_WIDTH > 0:
        cursor = min(BAR_WIDTH - 1, filled)
        chars[cursor] = ANIMATION_FRAMES[frame_index % len(ANIMATION_FRAMES)]

    return f"[{''.join(chars)}] {percent:3d}%"


def _state_label(payload: dict[str, object]) -> str:
    state = str(payload.get("execution_state", "IDLE")).strip().upper()
    if state not in {"IDLE", "RUNNING", "DONE", "FAILED"}:
        return "UNKNOWN"
    return state


def _result_text(payload: dict[str, object], state: str) -> str:
    explicit = str(payload.get("execution_result", "")).strip()
    if explicit:
        return explicit
    if state == "DONE":
        return "DONE - 可以下一步"
    if state == "FAILED":
        return "FAILED - 查看 ERROR"
    if state == "RUNNING":
        return "執行中..."
    return "等待執行"


def _screen(payload: dict[str, object], frame_index: int, branch: str, seconds_until_sync: float) -> str:
    project_percent = _clamped_int(payload.get("percent", 0))
    execution_percent = _clamped_int(payload.get("execution_percent", 0))
    state = _state_label(payload)
    animate = state == "RUNNING"

    lines = [
        "=" * 86,
        "                           AI LAB OS EXECUTION MONITOR",
        "=" * 86,
        f"BRANCH          = {branch}",
        f"MILESTONE       = {payload.get('milestone', 'unknown')}",
        f"PROJECT         = {project_percent}% overall",
        "",
        f"COMMAND         = {payload.get('execution_name', 'No active command')}",
        f"EXECUTION       {_progress_bar(execution_percent, frame_index, animate=animate)}",
        f"STATE           = {state}",
        "",
        f"CURRENT STEP    = {payload.get('execution_step', 'Waiting')}",
        f"DETAIL          = {payload.get('execution_detail', '')}",
        "",
        f"RESULT          = {_result_text(payload, state)}",
    ]

    error = str(payload.get("execution_error", "")).strip()
    if error:
        lines.append(f"ERROR           = {error}")

    lines.extend(
        [
            "",
            f"NEXT            = {payload.get('next_step', 'not specified')}",
            f"USER ACTION     = {payload.get('user_action', 'None')}",
            "",
            f"REMOTE SYNC     = {max(0.0, seconds_until_sync):4.1f}s   |   Ctrl+C to stop",
            "=" * 86,
        ]
    )
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
        "percent": 0,
        "execution_name": "Connecting",
        "execution_percent": 0,
        "execution_state": "RUNNING",
        "execution_step": "Fetching remote execution status",
        "execution_detail": "",
        "execution_result": "",
        "execution_error": "",
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
            shown["execution_state"] = "FAILED"
            shown["execution_error"] = f"Remote sync error: {last_error}"
            shown["execution_result"] = "FAILED - watcher will retry automatically"

        elapsed = time.monotonic() - last_sync
        remaining = poll_seconds - elapsed
        _clear_screen()
        print(_screen(shown, frame, branch, remaining), flush=True)
        frame += 1
        time.sleep(0.10)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live per-execution AI Lab OS progress monitor")
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
