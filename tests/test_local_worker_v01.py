from pathlib import Path

from ai_lab_os.local_worker import run_task
from ai_lab_os.worker_protocol import WorkerTask


class FakeBrain:
    def __init__(self, repository: Path):
        self.repository = repository
        self.calls = 0

    def repair(self, request):
        self.calls += 1
        (self.repository / "math_ops.py").write_text(
            "def multiply(a, b):\n    return a * b\n",
            encoding="utf-8",
        )
        return {"phase": "complete", "success": True}


def _init_repo(tmp_path: Path, branch: str = "main") -> Path:
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", branch], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    return tmp_path


def test_worker_runs_safe_pytest_and_completes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    result = run_task(
        WorkerTask(
            task_id="task-ok",
            repository_path=str(repo),
            branch="main",
            tests=("python -m pytest test_ok.py -q",),
        )
    )

    assert result.tests_passed is True
    assert result.status == "complete"
    assert result.attempts_used == 1


def test_worker_repairs_failed_test_via_brain(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "math_ops.py").write_text(
        "def multiply(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    (repo / "test_math_ops.py").write_text(
        "from math_ops import multiply\n\n"
        "def test_multiply():\n"
        "    assert multiply(6, 7) == 42\n",
        encoding="utf-8",
    )
    brain = FakeBrain(repo)

    result = run_task(
        WorkerTask(
            task_id="task-repair",
            repository_path=str(repo),
            branch="main",
            tests=("python -m pytest test_math_ops.py -q",),
            allow_cline_repair=True,
            allowed_files=("math_ops.py",),
            max_attempts=2,
        ),
        brain=brain,
    )

    assert brain.calls == 1
    assert result.tests_passed is True
    assert result.attempts_used == 2
    assert "math_ops.py" in result.changed_files


def test_worker_requires_allowed_files_for_repair(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "test_fail.py").write_text("def test_fail():\n    assert False\n", encoding="utf-8")

    result = run_task(
        WorkerTask(
            task_id="task-no-scope",
            repository_path=str(repo),
            branch="main",
            tests=("python -m pytest test_fail.py -q",),
            allow_cline_repair=True,
        )
    )

    assert result.status == "failed"
    assert result.error == "allowed_files required when Cline repair is enabled"
