from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from ai_lab_os.brain_client import BrainClient, BrainRepairRequest
from ai_lab_os.result_publisher import publish_result_file
from ai_lab_os.worker_protocol import WorkerResult, WorkerTask, load_task, write_result


RUNTIME_ARTIFACT_DIRS = {"__pycache__", ".pytest_cache"}


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


def _safe_pytest_argv(command: str) -> list[str]:
    parts = command.strip().split()
    if len(parts) < 3 or [p.lower() for p in parts[:3]] != ["python", "-m", "pytest"]:
        raise ValueError("only python -m pytest commands are allowed")
    if any(token in {"&&", "||", ";", "|", ">", ">>"} for token in parts):
        raise ValueError("shell operators are not allowed")
    return [sys.executable, "-m", "pytest", *parts[3:]]


def _clear_runtime_artifacts(repository: Path) -> None:
    """Remove disposable Python test caches before verification.

    Repair can rewrite a module within the same filesystem timestamp window
    while keeping the same file size. On Windows, an existing ``.pyc`` may
    then look current even though the source changed, causing the verification
    subprocess to execute stale bytecode. These directories are generated
    artifacts, so the worker removes them before every verification run.
    """
    for directory in repository.rglob("*"):
        if directory.is_dir() and directory.name in RUNTIME_ARTIFACT_DIRS:
            shutil.rmtree(directory, ignore_errors=True)


def _run_tests(task: WorkerTask, repository: Path) -> tuple[bool, str, str]:
    _clear_runtime_artifacts(repository)

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    for command in task.tests:
        completed = _run(_safe_pytest_argv(command), cwd=repository)
        stdout_parts.append(completed.stdout)
        stderr_parts.append(completed.stderr)
        if completed.returncode != 0:
            return False, "\n".join(stdout_parts), "\n".join(stderr_parts)
    return True, "\n".join(stdout_parts), "\n".join(stderr_parts)


def _changed_files(repository: Path) -> list[str]:
    completed = _run(["git", "status", "--porcelain"], cwd=repository)
    if completed.returncode != 0:
        return []

    changed: list[str] = []
    for line in completed.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().replace("\\", "/")
        parts = Path(path).parts
        if any(part in RUNTIME_ARTIFACT_DIRS for part in parts):
            continue
        changed.append(path)
    return changed


def run_task(task: WorkerTask, *, brain: BrainClient | None = None) -> WorkerResult:
    task.validate()
    repository = Path(task.repository_path).resolve()
    if not repository.exists() or not repository.is_dir():
        return WorkerResult(
            task_id=task.task_id,
            status="failed",
            tests_passed=False,
            error="repository_path does not exist",
        )

    branch_check = _run(["git", "branch", "--show-current"], cwd=repository)
    current_branch = branch_check.stdout.strip()
    if branch_check.returncode != 0 or current_branch != task.branch:
        return WorkerResult(
            task_id=task.task_id,
            status="failed",
            tests_passed=False,
            error=f"expected branch {task.branch!r}, found {current_branch!r}",
        )

    passed, stdout, stderr = _run_tests(task, repository)
    attempts = 1

    if not passed and task.allow_cline_repair:
        if not task.allowed_files:
            return WorkerResult(
                task_id=task.task_id,
                status="failed",
                tests_passed=False,
                attempts_used=attempts,
                stdout=stdout,
                stderr=stderr,
                error="allowed_files required when Cline repair is enabled",
            )
        client = brain or BrainClient()
        client.repair(
            BrainRepairRequest(
                task=(
                    "Repair the failing test suite for this local worker task. "
                    "Use the test output as evidence and make the smallest safe change."
                ),
                repository_path=str(repository),
                tests=task.tests,
                allowed_files=task.allowed_files,
                max_attempts=task.max_attempts,
            )
        )
        attempts += 1
        passed, stdout, stderr = _run_tests(task, repository)

    return WorkerResult(
        task_id=task.task_id,
        status="complete" if passed else "failed",
        tests_passed=passed,
        attempts_used=attempts,
        changed_files=_changed_files(repository),
        stdout=stdout,
        stderr=stderr,
        error=None if passed else "verification failed",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Lab OS local worker")
    parser.add_argument("task_file")
    parser.add_argument("--result", required=True)
    parser.add_argument(
        "--publish-result",
        action="store_true",
        help="commit and push only the generated results/ file on the current branch",
    )
    args = parser.parse_args()

    task = load_task(args.task_file)
    result = run_task(task)
    write_result(args.result, result)
    print(f"TASK = {result.task_id}")
    print(f"STATUS = {result.status}")
    print(f"TESTS PASSED = {result.tests_passed}")
    print(f"ATTEMPTS = {result.attempts_used}")
    print(f"CHANGED FILES = {', '.join(result.changed_files)}")
    if result.error:
        print(f"ERROR = {result.error}")

    if args.publish_result:
        published = publish_result_file(args.result)
        print(f"RESULT COMMITTED = {published.committed}")
        print(f"RESULT PUSHED = {published.pushed}")
        print(f"RESULT BRANCH = {published.branch}")
        if published.commit_sha:
            print(f"RESULT COMMIT = {published.commit_sha}")
        if published.message:
            print(f"RESULT PUBLISH MESSAGE = {published.message}")

    return 0 if result.tests_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
