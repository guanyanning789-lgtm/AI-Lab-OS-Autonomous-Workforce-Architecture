from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class BrainRepairRequest:
    task: str
    repository_path: str
    tests: tuple[str, ...]
    allowed_files: tuple[str, ...]
    max_attempts: int = 2
    timeout_seconds: int = 180


class BrainClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def repair(self, request: BrainRepairRequest) -> dict:
        payload = {
            "task": request.task,
            "repository_path": request.repository_path,
            "tests": list(request.tests),
            "allowed_files": list(request.allowed_files),
            "approved": True,
            "auto_approve_tools": True,
            "max_attempts": request.max_attempts,
            "timeout_seconds": request.timeout_seconds,
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            self.base_url + "/coding-agent/run",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout_seconds + 30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Brain API returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Brain API is unavailable: {exc.reason}") from exc
