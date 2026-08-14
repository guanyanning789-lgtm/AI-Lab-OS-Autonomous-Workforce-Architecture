import json

import pytest

from ai_lab_os.worker_protocol import WorkerResult, load_task, write_result


def test_load_task_accepts_safe_pytest(tmp_path):
    path = tmp_path / "task.json"
    path.write_text(
        json.dumps(
            {
                "task_id": "task-0001",
                "repository_path": r"C:\AI-Lab\brain",
                "branch": "ai/v1.1-coding-agent",
                "goal": "Fix the example implementation.",
                "success_criteria": ["Configured pytest command passes."],
                "tests": ["python -m pytest -q"],
                "allow_cline_repair": True,
                "allowed_files": ["app/example.py"],
                "max_attempts": 2,
            }
        ),
        encoding="utf-8",
    )

    task = load_task(path)

    assert task.task_id == "task-0001"
    assert task.goal == "Fix the example implementation."
    assert task.success_criteria == ("Configured pytest command passes.",)
    assert task.allow_cline_repair is True
    assert task.allowed_files == ("app/example.py",)


def test_load_task_rejects_arbitrary_command(tmp_path):
    path = tmp_path / "task.json"
    path.write_text(
        json.dumps(
            {
                "task_id": "task-0002",
                "repository_path": "repo",
                "branch": "main",
                "tests": ["powershell Remove-Item important.txt"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="only python -m pytest"):
        load_task(path)


def test_write_result_creates_json(tmp_path):
    target = tmp_path / "results" / "task.json"
    write_result(
        target,
        WorkerResult(
            task_id="task-0003",
            status="complete",
            tests_passed=True,
            changed_files=["app/main.py"],
        ),
    )

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["status"] == "complete"
    assert data["tests_passed"] is True
