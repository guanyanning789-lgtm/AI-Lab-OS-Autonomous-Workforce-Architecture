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
    """Generic HTTP transport for a computer action service."""

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
        return self._post(payload)

    def _post(self, payload: dict[str, object]) -> dict[str, object]:
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


class BrainWindowsE2EBackend(HttpComputerBackend):
    """Adapter for the real AI Lab Brain /task/windows/e2e contract.

    The Brain endpoint accepts step actions click/type/hotkey. In safe mode the
    adapter always sends mock=true and allow_real_actions=false. A Computer task
    must explicitly provide metadata['action']; optional metadata['args_json'] can
    carry action arguments as a JSON object.
    """

    ALLOWED_ACTIONS = {"click", "type", "hotkey"}

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        path: str = "/task/windows/e2e",
        timeout_seconds: int = 60,
    ) -> None:
        super().__init__(base_url, path=path, timeout_seconds=timeout_seconds)

    def execute(self, request: ComputerActionRequest) -> dict[str, object]:
        action = request.metadata.get("action", "").strip().lower()
        if action not in self.ALLOWED_ACTIONS:
            raise RuntimeError(
                "Computer task metadata.action must be one of: click, type, hotkey"
            )

        raw_args = request.metadata.get("args_json", "").strip()
        args: dict[str, object] = {}
        if raw_args:
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Computer task metadata.args_json must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise RuntimeError("Computer task metadata.args_json must decode to an object")
            args = parsed

        step: dict[str, object] = {
            "step_id": 1,
            "action": action,
            "args": args,
        }
        window_title = request.metadata.get("window_title", "").strip()
        if window_title:
            step["window_title"] = window_title
        expected_process = request.metadata.get("expected_process", "").strip()
        if expected_process:
            step["expected_process"] = expected_process

        payload: dict[str, object] = {
            "task_id": request.task_id,
            "steps": [step],
            "mock": request.dry_run or not request.approved,
            "allow_real_actions": request.approved and not request.dry_run,
        }
        return self._post(payload)


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
            errors = response.get("errors")
            if isinstance(errors, list) and errors:
                success = False

        message = str(
            response.get("message")
            or response.get("detail")
            or ("computer task completed" if success else "computer task failed")
        )
        return TaskExecutionResult(
            status=TaskExecutionStatus.SUCCESS if bool(success) else TaskExecutionStatus.FAILED,
            message=message,
        )
