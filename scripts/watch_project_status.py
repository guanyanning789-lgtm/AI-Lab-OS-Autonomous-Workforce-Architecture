from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


DEFAULT_BRANCH = "ai/v0.3-supervisor-runtime"
STATUS_PATH = "status/project_status.json"
BAR_WIDTH = 46


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

    if not isinstance(show.stdout, str) or not show.stdout.strip():
        raise RuntimeError("remote status file returned no text")
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


def _progress_bar(percent: int) -> str:
    filled = int(BAR_WIDTH * percent / 100)
    return f"[{'█' * filled}{'·' * (BAR_WIDTH - filled)}] {percent:3d}%"


def _state_label(payload: dict[str, object]) -> str:
    state = str(payload.get("execution_state", "IDLE")).strip().upper()
    return state if state in {"IDLE", "RUNNING", "DONE", "FAILED"} else "UNKNOWN"


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


def _render(payload: dict[str, object], branch: str, sync_note: str) -> str:
    project_percent = _clamped_int(payload.get("percent", 0))
    execution_percent = _clamped_int(payload.get("execution_percent", 0))
    state = _state_label(payload)
    lines = [
        "=" * 86,
        "                           AI LAB OS EXECUTION MONITOR",
        "=" * 86,
        f"BRANCH          = {branch}",
        f"MILESTONE       = {payload.get('milestone', 'unknown')}",
        f"PROJECT         = {project_percent}% overall",
        "",
        f"COMMAND         = {payload.get('execution_name', 'No active command')}",
        f"EXECUTION       {_progress_bar(execution_percent)}",
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
    lines.extend([
        "",
        f"NEXT            = {payload.get('next_step', 'not specified')}",
        f"USER ACTION     = {payload.get('user_action', 'None')}",
        "",
        f"SYNC            = {sync_note}",
        "=" * 86,
    ])
    return "\n".join(lines)


def watch(repository: Path, branch: str, poll_seconds: float) -> None:
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be > 0")

    last_payload: dict[str, object] | None = None
    last_fingerprint: str | None = None
    print("Connecting to GitHub remote status...", flush=True)

    while True:
        try:
            payload = _fetch_status(repository, branch)
            fingerprint = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if fingerprint != last_fingerprint:
                print("\n" + _render(payload, branch, "updated from GitHub"), flush=True)
                last_payload = payload
                last_fingerprint = fingerprint
        except Exception as exc:
            # Do not redraw the whole screen or replace the real execution state.
            # A transient sync failure is a watcher issue, not a task failure.
            print(f"\n[watcher sync warning] {exc} -- retrying in {poll_seconds:g}s", flush=True)
            if last_payload is None:
                print("No remote status has been loaded yet.", flush=True)
        time.sleep(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stable per-execution AI Lab OS progress monitor")
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
