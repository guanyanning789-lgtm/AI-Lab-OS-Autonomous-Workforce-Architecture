from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask


@dataclass(frozen=True)
class ResearchSource:
    title: str
    url: str
    content: str = ""


@dataclass(frozen=True)
class ResearchResponse:
    query: str
    sources: tuple[ResearchSource, ...]


UrlOpen = Callable[..., object]


class SearXNGResearchClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        *,
        timeout_seconds: int = 30,
        opener: UrlOpen | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.urlopen

    def search(self, query: str, *, limit: int = 5) -> ResearchResponse:
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("research query cannot be empty")
        if limit < 1:
            raise ValueError("limit must be >= 1")

        params = urllib.parse.urlencode({"q": cleaned, "format": "json"})
        request = urllib.request.Request(
            f"{self.base_url}/search?{params}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"SearXNG returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"SearXNG is unavailable: {exc.reason}") from exc

        raw_results = payload.get("results", []) if isinstance(payload, dict) else []
        sources: list[ResearchSource] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            sources.append(
                ResearchSource(
                    title=str(item.get("title", "")).strip(),
                    url=url,
                    content=str(item.get("content", "")).strip(),
                )
            )
            if len(sources) >= limit:
                break

        return ResearchResponse(query=cleaned, sources=tuple(sources))


class ResearchExecutor:
    def __init__(self, client: SearXNGResearchClient | None = None, *, max_sources: int = 5) -> None:
        if max_sources < 1:
            raise ValueError("max_sources must be >= 1")
        self.client = client or SearXNGResearchClient()
        self.max_sources = max_sources

    def __call__(self, task: PlannedTask) -> TaskExecutionResult:
        if task.agent is not AgentKind.RESEARCH:
            return TaskExecutionResult(
                status=TaskExecutionStatus.FAILED,
                message=f"ResearchExecutor cannot execute agent={task.agent.value}",
            )

        query = task.metadata.get("query", "").strip() or task.description.strip()
        try:
            response = self.client.search(query, limit=self.max_sources)
        except Exception as exc:
            return TaskExecutionResult(
                status=TaskExecutionStatus.FAILED,
                message=f"research failed: {exc}",
            )

        if not response.sources:
            return TaskExecutionResult(
                status=TaskExecutionStatus.FAILED,
                message=f"research returned no sources for query: {response.query}",
            )

        evidence = {
            "query": response.query,
            "sources": [
                {
                    "title": source.title,
                    "url": source.url,
                    "content": source.content,
                }
                for source in response.sources
            ],
        }
        return TaskExecutionResult(
            status=TaskExecutionStatus.SUCCESS,
            message=json.dumps(evidence, ensure_ascii=False, separators=(",", ":")),
        )
