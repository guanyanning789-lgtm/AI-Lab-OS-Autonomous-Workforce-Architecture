from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import ai_lab_os.worker_daemon as daemon_module
from ai_lab_os.worker_daemon import (
    DaemonConfig,
    WorkerCodeUpdated,
    discover_pending_tasks,
    process_once,
)
from ai_lab_os.worker_protocol import WorkerResult


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    (tmp_path / "tasks").mkdir()
    (tmp_path / "results").mkdir()
    return tmp_path


def _write_task(repo: Path, name: str, task_id: str) -> Path:
    path = repo / "tasks" / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "repository_path": str(repo),
                "branch": "main",
                "tests": ["python -m pytest -q"],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_discover_pending_tasks_skips_existing_results(tmp_path):
    repo = _init_repo(tmp_path)
    first = _write_task(repo, "task-0001", "one")
    second = _write_task(repo, "task-0002", "two")
    (repo / "results" / "task-0001.json").write_text("{}", encoding="utf-8")

    pending = discover_pending_tasks(DaemonConfig(repository_path=str(repo), pull_before_scan=False))

    assert pending == [second]
    assert first not in pending


def test_process_once_runs_pending_task_and_writes_result(monkeypatch, tmp_path):
    repo = _init_repo(tmp_path)
    _write_task(repo, "task-0002", "two")
    calls = []

    def fake_run_task(task, *, progress=None):
        calls.append(task.task_id)
        if progress:
            progress("VERIFYING_INITIAL")
        return WorkerResult(task_id=task.task_id, status="complete", tests_passed=True, attempts_used=1)

    monkeypatch.setattr(daemon_module, "run_task", fake_run_task)

    processed = process_once(
        DaemonConfig(repository_path=str(repo), pull_before_scan=False, publish_results=False)
    )

    assert processed == ["two"]
    assert calls == ["two"]
    result = json.loads((repo / "results" / "task-0002.json").read_text(encoding="utf-8"))
    assert result["status"] == "complete"
    assert result["tests_passed"] is True


def test_process_once_publishes_when_enabled(monkeypatch, tmp_path):
    repo = _init_repo(tmp_path)
    _write_task(repo, "task-0003", "three")
    published = []

    monkeypatch.setattr(
        daemon_module,
        "run_task",
        lambda task, progress=None: WorkerResult(task_id=task.task_id, status="complete", tests_passed=True),
    )
    monkeypatch.setattr(
        daemon_module,
        "publish_result_file",
        lambda result_path: published.append(Path(result_path)),
    )

    processed = process_once(
        DaemonConfig(repository_path=str(repo), pull_before_scan=False, publish_results=True)
    )

    assert processed == ["three"]
    assert published == [(repo / "results" / "task-0003.json").resolve()]


def test_process_once_requests_restart_when_pull_changes_head(monkeypatch, tmp_path):
    repo = _init_repo(tmp_path)
    monkeypatch.setattr(daemon_module, "_safe_pull", lambda repository: True)

    with pytest.raises(WorkerCodeUpdated, match="updated"):
        process_once(DaemonConfig(repository_path=str(repo), pull_before_scan=True))


def test_terminal_surfaces_user_verification_request(capsys, tmp_path):
    repo = _init_repo(tmp_path)
    verification = repo / "verification"
    verification.mkdir()
    (verification / "request.json").write_text(
        json.dumps(
            {
                "task_id": "task-real-e2e",
                "title": "Cline real-machine validation",
                "message": "Keep Brain and Daemon running, then open ChatGPT.",
            }
        ),
        encoding="utf-8",
    )

    processed = process_once(
        DaemonConfig(
            repository_path=str(repo),
            pull_before_scan=False,
            publish_results=False,
            sync_managed_repositories=False,
        )
    )

    output = capsys.readouterr().out
    assert processed == []
    assert "USER VERIFICATION REQUIRED" in output
    assert "task-real-e2e" in output
    assert "Cline real-machine validation" in output
    assert "Keep Brain and Daemon running" in output
