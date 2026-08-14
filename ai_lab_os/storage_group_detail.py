from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupItem, CleanupPlan
from ai_lab_os.storage_decision_groups import DecisionGroup


@dataclass(frozen=True)
class GroupDetail:
    key: str
    item_count: int
    total_bytes: int
    actions: tuple[tuple[str, int], ...]
    destinations: tuple[str, ...]
    rollback_capable: bool
    risk: str
    examples: tuple[str, ...]


def build_group_detail(group: DecisionGroup, plan: CleanupPlan, *, max_examples: int = 12) -> GroupDetail:
    by_path: dict[str, CleanupItem] = {item.path: item for item in plan.items}
    items = tuple(by_path[path] for path in group.paths if path in by_path)

    action_counts: dict[str, int] = {}
    destinations: set[str] = set()
    total_bytes = 0
    rollback_capable = True

    for item in items:
        action_counts[item.action.value] = action_counts.get(item.action.value, 0) + 1
        total_bytes += max(0, item.bytes_affected)
        if item.destination:
            destinations.add(str(Path(item.destination).parent))
        if item.action.value in {"review", "block", "keep"}:
            rollback_capable = False

    if any(name in {"delete_duplicate", "clean"} for name in action_counts):
        risk = "MEDIUM - cleanup candidates require explicit approval and quarantine before permanent deletion"
    elif any(name in {"migrate", "archive"} for name in action_counts):
        risk = "MEDIUM - path changes may affect references; collision guard and post-action verification required"
    elif action_counts.get("review"):
        risk = "HIGH - review-only items are not executable"
    else:
        risk = "LOW - informational/protected group"

    examples = tuple(group.paths[: max(1, max_examples)])
    return GroupDetail(
        key=group.key,
        item_count=group.item_count,
        total_bytes=total_bytes,
        actions=tuple(sorted(action_counts.items())),
        destinations=tuple(sorted(destinations)),
        rollback_capable=rollback_capable,
        risk=risk,
        examples=examples,
    )


def render_group_details(groups: tuple[DecisionGroup, ...], plan: CleanupPlan, *, max_examples: int = 5) -> str:
    lines = ["GROUP DETAILS:"]
    for index, group in enumerate(groups, 1):
        detail = build_group_detail(group, plan, max_examples=max_examples)
        lines.append(f"  {index:02d}. {group.key}")
        lines.append(f"      items      = {detail.item_count}")
        lines.append(f"      size       = {detail.total_bytes / (1024 ** 3):.3f} GB")
        lines.append("      actions    = " + (", ".join(f"{name}:{count}" for name, count in detail.actions) or "none"))
        lines.append("      targets    = " + (", ".join(detail.destinations) or "none / review only"))
        lines.append(f"      rollback   = {'YES' if detail.rollback_capable else 'NOT YET / REVIEW'}")
        lines.append(f"      risk       = {detail.risk}")
        for path in detail.examples:
            lines.append(f"      - {path}")
        if detail.item_count > len(detail.examples):
            lines.append(f"      ... {detail.item_count - len(detail.examples)} more items")
    return "\n".join(lines)
