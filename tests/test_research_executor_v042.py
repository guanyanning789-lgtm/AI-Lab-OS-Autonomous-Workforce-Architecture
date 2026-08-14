from __future__ import annotations

import io
import json
import urllib.error

from ai_lab_os.models import AgentKind
from ai_lab_os.research_executor import ResearchExecutor, SearXNGResearchClient
from ai_lab_os.supervisor_loop import TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind


class _Response:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _task(agent: AgentKind = AgentKind.RESEARCH, *, metadata: dict[str, str] | None = None) -> PlannedTask:
    return PlannedTask(
        task_id="goal-v042-task-001",
        goal_id="goal-v042",
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description="Find current evidence about the target technology",
        agent=agent,
        metadata=metadata or {},
    )


def test_research_executor_returns_structured_source_evidence() -> None:
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return _Response(
            {
                "results": [
                    {"title": "Source A", "url": "https://example.com/a", "content": "Evidence A"},
                    {"title": "Source B", "url": "https://example.com/b", "content": "Evidence B"},
                ]
            }
        )

    client = SearXNGResearchClient("http://127.0.0.1:8080", opener=opener)
    result = ResearchExecutor(client)(_task(metadata={"query": "latest agent runtime"}))

    assert result.status is TaskExecutionStatus.SUCCESS
    payload = json.loads(result.message)
    assert payload["query"] == "latest agent runtime"
    assert [item["url"] for item in payload["sources"]] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert "q=latest+agent+runtime" in seen["url"]
    assert "format=json" in seen["url"]


def test_research_executor_fails_closed_for_non_research_agent() -> None:
    result = ResearchExecutor()(_task(AgentKind.CODING))
    assert result.status is TaskExecutionStatus.FAILED
    assert "cannot execute" in result.message


def test_research_executor_fails_when_no_sources_are_returned() -> None:
    client = SearXNGResearchClient(opener=lambda request, timeout: _Response({"results": []}))
    result = ResearchExecutor(client)(_task())
    assert result.status is TaskExecutionStatus.FAILED
    assert "no sources" in result.message


def test_research_executor_converts_backend_error_to_failed_result() -> None:
    def opener(request, timeout):
        raise urllib.error.URLError("offline")

    client = SearXNGResearchClient(opener=opener)
    result = ResearchExecutor(client)(_task())
    assert result.status is TaskExecutionStatus.FAILED
    assert "SearXNG is unavailable" in result.message


def test_research_client_respects_max_sources() -> None:
    client = SearXNGResearchClient(
        opener=lambda request, timeout: _Response(
            {
                "results": [
                    {"title": "1", "url": "https://example.com/1"},
                    {"title": "2", "url": "https://example.com/2"},
                    {"title": "3", "url": "https://example.com/3"},
                ]
            }
        )
    )
    response = client.search("query", limit=2)
    assert len(response.sources) == 2
