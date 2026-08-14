from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WorkerTask:
    task_id: str
    repository_path: str
    branch: str
    goal: str = ""
    success_criteria: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    allow_cline_repair: bool = False
    allowed_files: tuple[str, ...] = ()
    max_attempts: int = 2

    def validate(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id cannot be empty")
        if not self.repository_path.strip():
            raise ValueError("repository_path cannot be empty")
        if not self.branch.strip():
            raise ValueError("branch cannot be empty")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        for command in self.tests:
            if not command.strip().lower().startswith("python -m pytest"):
                raise ValueError("only python -m pytest commands are allowed")


@dataclass
class WorkerResult:
    task_id: str
    status: str
    tests_passed: bool
    attempts_used: int = 1
    changed_files: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


def load_task(path: str | Path) -> WorkerTask:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    task = WorkerTask(
        task_id=str(data["task_id"]),
        repository_path=str(data["repository_path"]),
        branch=str(data["branch"]),
        goal=str(data.get("goal", "")),
        success_criteria=tuple(str(item) for item in data.get("success_criteria", [])),
        tests=tuple(data.get("tests", [])),
        allow_cline_repair=bool(data.get("allow_cline_repair", False)),
        allowed_files=tuple(data.get("allowed_files", [])),
        max_attempts=int(data.get("max_attempts", 2)),
    )
    task.validate()
    return task


def write_result(path: str | Path, result: WorkerResult) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
