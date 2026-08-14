from __future__ import annotations

import argparse
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ai_lab_os.local_worker import run_task
from ai_lab_os.result_publisher import publish_result_file
from ai_lab_os.worker_protocol import load_task, write_result


SleepFn = Callable[[float], None]


@dataclass(frozen=True)
class DaemonConfig:
    repository_path: str
    tasks_dir: str = "tasks"
    results_dir: str = "results"
    poll_seconds: float = 15.0
    publish_results: bool = True
    pull_before_scan: bool = True


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


def _safe_pull(repository: Path) -> None:
    status = _run_git(["status", "--porcelain"], cwd=repository)
    if status.returncode != 0:
        raise RuntimeError((status.stderr or "").strip() or "git status failed")
    if (status.stdout or "").strip():
        raise RuntimeError("worker repository must be clean before automatic pull")

    pull = _run_git(["pull", "--ff-only"], cwd=repository)
    if pull.returncode != 0:
        raise RuntimeError((pull.stderr or "").strip() or (pull.stdout or "").strip() or "git pull failed")


def discover_pending_tasks(config: DaemonConfig) -> list[Path]:
    repository = Path(config.repository_path).resolve()
    tasks_root = repository / config.tasks_dir
    results_root = repository / config.results_dir

    if not tasks_root.exists():
        return []

    pending: list[Path] = []
    for task_path in sorted(tasks_root.glob("*.json")):
        load_task(task_path)
        result_path = results_root / f"{task_path.stem}.json"
        if result_path.exists():
            continue
        pending.append(task_path)
    return pending


def process_once(config: DaemonConfig) -> list[str]:
    repository = Path(config.repository_path).resolve()
    if config.pull_before_scan:
        _safe_pull(repository)

    processed: list[str] = []
    for task_path in discover_pending_tasks(config):
        task = load_task(task_path)
        result_path = repository / config.results_dir / f"{task_path.stem}.json"
        print(f"PICKED = {task.task_id}", flush=True)
        result = run_task(
            task,
            progress=lambda event, task_id=task.task_id: print(
                f"TASK {task_id} = {event}",
                flush=True,
            ),
        )
        print(
            f"TASK {task.task_id} RESULT = {result.status} | tests_passed={result.tests_passed}",
            flush=True,
        )
        write_result(result_path, result)

        if config.publish_results:
            print(f"PUBLISHING = {task.task_id}", flush=True)
            publish_result_file(result_path)
            print(f"PUBLISHED = {task.task_id}", flush=True)

        processed.append(task.task_id)
    return processed


def run_daemon(config: DaemonConfig, *, sleep_fn: SleepFn = time.sleep) -> None:
    if config.poll_seconds <= 0:
        raise ValueError("poll_seconds must be > 0")

    while True:
        try:
            processed = process_once(config)
            if processed:
                print("PROCESSED = " + ", ".join(processed), flush=True)
            else:
                print("IDLE = no pending tasks", flush=True)
        except Exception as exc:
            print(f"WORKER ERROR = {exc}", flush=True)
        sleep_fn(config.poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Lab OS local worker daemon")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--no-pull", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    config = DaemonConfig(
        repository_path=args.repo,
        poll_seconds=args.poll_seconds,
        publish_results=not args.no_publish,
        pull_before_scan=not args.no_pull,
    )

    if args.once:
        processed = process_once(config)
        print("PROCESSED = " + (", ".join(processed) if processed else "none"))
        return 0

    run_daemon(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
