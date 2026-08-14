from __future__ import annotations

import argparse
import hashlib
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
    for directory in repository.rglob("*"):
        if directory.is_dir() and directory.name in RUNTIME_ARTIFACT_DIRS:
            shutil.rmtree(directory, ignore_errors=True)


def _run_tests(task: WorkerTask, repository: Path) -> tuple[bool, str, str]:
    _clear_runtime_artifacts(repository)

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    for command in task.tests:
        completed = _run(_safe_pytest_argv(command), cwd=repository)
        stdout_parts.append(completed.stdout or "")
        stderr_parts.append(completed.stderr or "")
        if completed.returncode != 0:
            return False, "\n".join(stdout_parts), "\n".join(stderr_parts)
    return True, "\n".join(stdout_parts), "\n".join(stderr_parts)


def _file_digest(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_allowed_files(repository: Path, allowed_files: tuple[str, ...]) -> dict[str, str | None]:
    return {
        relative.replace("\\", "/"): _file_digest(repository / relative)
        for relative in allowed_files
    }


def _changed_allowed_files(
    repository: Path,
    before: dict[str, str | None],
) -> list[str]:
    changed: list[str] = []
    for relative, previous_digest in before.items():
        if _file_digest(repository / relative) != previous_digest:
            changed.append(relative)
    return sorted(changed)


def _repair_prompt(task: WorkerTask, stdout: str, stderr: str) -> str:
    goal = task.goal.strip() or "Repair the failing test suite for this local worker task."
    criteria = "\n".join(f"- {item}" for item in task.success_criteria) or "- All configured pytest verification commands must pass."
    allowed = "\n".join(f"- {path}" for path in task.allowed_files)
    evidence_parts = [part.strip() for part in (stdout, stderr) if part.strip()]
    evidence = "\n\n".join(evidence_parts) or "No test output was captured."
    return (
        f"Task goal:\n{goal}\n\n"
        f"Allowed files (do not modify anything else):\n{allowed}\n\n"
        f"Success criteria:\n{criteria}\n\n"
        f"Current verification failure:\n{evidence}\n\n"
        "Use the failure output as evidence. Make the smallest safe code change required to satisfy the task. "
        "Do not modify tests unless a test file is explicitly listed in Allowed files."
    )


def _brain_fields(response: dict | None) -> tuple[str | None, bool | None, str | None, list[str]]:
    if not isinstance(response, dict):
        return None, None, None, []
    phase = response.get("phase")
    success = response.get("success")
    message = response.get("message")
    verification_errors = response.get("verification_errors", [])
    return (
        str(phase) if phase is not None else None,
        bool(success) if success is not None else None,
        str(message) if message is not None else None,
        [str(item) for item in verification_errors] if isinstance(verification_errors, list) else [],
    )


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
    current_branch = (branch_check.stdout or "").strip()
    if branch_check.returncode != 0 or current_branch != task.branch:
        return WorkerResult(
            task_id=task.task_id,
            status="failed",
            tests_passed=False,
            error=f"expected branch {task.branch!r}, found {current_branch!r}",
        )

    allowed_before = _snapshot_allowed_files(repository, task.allowed_files)
    passed, stdout, stderr = _run_tests(task, repository)
    attempts = 1
    brain_phase: str | None = None
    brain_success: bool | None = None
    brain_message: str | None = None
    brain_verification_errors: list[str] = []

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
        response = client.repair(
            BrainRepairRequest(
                task=_repair_prompt(task, stdout, stderr),
                repository_path=str(repository),
                tests=task.tests,
                allowed_files=task.allowed_files,
                max_attempts=task.max_attempts,
            )
        )
        attempts += 1
        brain_phase, brain_success, brain_message, brain_verification_errors = _brain_fields(response)

        if brain_success is False:
            return WorkerResult(
                task_id=task.task_id,
                status="failed",
                tests_passed=False,
                attempts_used=attempts,
                changed_files=_changed_allowed_files(repository, allowed_before),
                stdout=stdout,
                stderr=stderr,
                error="Brain repair failed",
                brain_phase=brain_phase,
                brain_success=brain_success,
                brain_message=brain_message,
                brain_verification_errors=brain_verification_errors,
            )

        passed, stdout, stderr = _run_tests(task, repository)

    return WorkerResult(
        task_id=task.task_id,
        status="complete" if passed else "failed",
        tests_passed=passed,
        attempts_used=attempts,
        changed_files=_changed_allowed_files(repository, allowed_before),
        stdout=stdout,
        stderr=stderr,
        error=None if passed else "verification failed",
        brain_phase=brain_phase,
        brain_success=brain_success,
        brain_message=brain_message,
        brain_verification_errors=brain_verification_errors,
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
    if result.brain_phase:
        print(f"BRAIN PHASE = {result.brain_phase}")
    if result.brain_message:
        print(f"BRAIN MESSAGE = {result.brain_message}")
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
