from ai_lab_os.observability import InMemoryEventLog, TaskEvent
from ai_lab_os.reliability import ReliabilityPolicy


def test_reliability_requires_approval_for_external_side_effects():
    policy = ReliabilityPolicy()
    decision = policy.evaluate(
        risk="low",
        has_external_side_effects=True,
        approved=False,
    )

    assert decision.allowed is False
    assert decision.requires_approval is True


def test_reliability_allows_approved_external_side_effects():
    policy = ReliabilityPolicy()
    decision = policy.evaluate(
        risk="medium",
        has_external_side_effects=True,
        approved=True,
    )

    assert decision.allowed is True


def test_retry_budget():
    policy = ReliabilityPolicy(max_retries=2)

    assert policy.can_retry(0) is True
    assert policy.can_retry(1) is True
    assert policy.can_retry(2) is False


def test_event_log_filters_by_task():
    log = InMemoryEventLog()
    log.append(TaskEvent("task-1", "started", "started"))
    log.append(TaskEvent("task-2", "started", "started"))
    log.append(TaskEvent("task-1", "verified", "pass", step_id=1))

    events = log.for_task("task-1")

    assert [event.event_type for event in events] == ["started", "verified"]
