from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask


@dataclass(frozen=True)
class ComputerActionRequest:
    task_id: str
    instruction: str
    success_criteria: tuple[str, ...]
    metadata: dict[str, str]
    approved: bool = False
    dry_run: bool = True


class ComputerBackend(Protocol):
    def execute(self, request: ComputerActionRequest) -> dict[str, object]: ...


class HttpComputerBackend:
    """HTTP transport for a local Windows/computer action service.

    The endpoint is intentionally configurable because the real Windows host may
    live in a separate local process/repository. Safe defaults keep requests in
    dry-run and unapproved mode until a local E2E explicitly opts in.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        path: str = "/computer/execute",
        timeout_seconds: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.path = "/" + path.lstrip("/")
        self.timeout_seconds = timeout_seconds

    def execute(self, request: ComputerActionRequest) -> dict[str, object]:
        payload = {
            "task_id": request.task_id,
            "instruction": request.instruction,
            "success_criteria": list(request.success_criteria),
            "metadata": dict(request.metadata),
            "approved": request.approved,
            "dry_run": request.dry_run,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(
            self.base_url + self.path,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Computer backend returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Computer backend is unavailable: {exc.reason}") from exc

        if not isinstance(data, dict):
            raise RuntimeError("Computer backend response must be a JSON object")
        return data


@dataclass
class ComputerExecutor:
    backend: ComputerBackend
    approved: bool = False
    dry_run: bool = True

    def __call__(self, task: PlannedTask) -> TaskExecutionResult:
        if task.agent is not AgentKind.COMPUTER:
            return TaskExecutionResult(
                status=TaskExecutionStatus.FAILED,
                message=f"ComputerExecutor refuses non-computer agent: {task.agent.value}",
            )

        request = ComputerActionRequest(
            task_id=task.task_id,
            instruction=task.description,
            success_criteria=task.success_criteria,
            metadata=dict(task.metadata),
            approved=self.approved,
            dry_run=self.dry_run,
        )
        try:
            response = self.backend.execute(request)
        except Exception as exc:
            return TaskExecutionResult(
                status=TaskExecutionStatus.FAILED,
                message=f"computer backend error: {exc}",
            )

        success = response.get("success")
        if success is None:
            status = str(response.get("status", "")).strip().lower()
            success = status in {"success", "complete", "completed", "pass", "passed"}

        message = str(
            response.get("message")
            or response.get("detail")
            or ("computer task completed" if success else "computer task failed")
        )
        return TaskExecutionResult(
            status=TaskExecutionStatus.SUCCESS if bool(success) else TaskExecutionStatus.FAILED,
            message=message,
        )
