from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction, CleanupPlan
from ai_lab_os.storage_intelligence import VersionFamily


class DecisionGroupKind(str, Enum):
    VERSION_FAMILY = "version_family"
    DOWNLOADS_BATCH = "downloads_batch"
    DESKTOP_BATCH = "desktop_batch"
    DUPLICATE_GROUP = "duplicate_group"
    OTHER = "other"


@dataclass(frozen=True)
class DecisionGroup:
    key: str
    kind: DecisionGroupKind
    item_count: int
    approval_required: bool
    summary: str
    paths: tuple[str, ...]


def _under(path: str, needle: str) -> bool:
    parts = {part.lower() for part in Path(path).parts}
    return needle.lower() in parts


def build_decision_groups(plan: CleanupPlan, families: tuple[VersionFamily, ...]) -> tuple[DecisionGroup, ...]:
    grouped_paths: set[str] = set()
    groups: list[DecisionGroup] = []

    for family in families:
        paths = tuple(item.path for item in family.members)
        grouped_paths.update(paths)
        groups.append(
            DecisionGroup(
                key=f"family:{family.family}",
                kind=DecisionGroupKind.VERSION_FAMILY,
                item_count=len(paths),
                approval_required=True,
                summary=f"{family.family}: keep latest v{family.latest.raw_version}; review/archive {len(family.historical)} historical versions",
                paths=paths,
            )
        )

    duplicate_items = tuple(item for item in plan.items if item.action is CleanupAction.DELETE_DUPLICATE and item.path not in grouped_paths)
    if duplicate_items:
        paths = tuple(item.path for item in duplicate_items)
        grouped_paths.update(paths)
        groups.append(DecisionGroup("duplicates", DecisionGroupKind.DUPLICATE_GROUP, len(paths), True, f"{len(paths)} duplicate cleanup candidates require review", paths))

    for label, kind in (("Downloads", DecisionGroupKind.DOWNLOADS_BATCH), ("Desktop", DecisionGroupKind.DESKTOP_BATCH)):
        items = tuple(
            item for item in plan.items
            if item.path not in grouped_paths
            and item.approval_required
            and _under(item.path, label)
            and item.action in {CleanupAction.MIGRATE, CleanupAction.ARCHIVE, CleanupAction.CLEAN, CleanupAction.REVIEW}
        )
        if items:
            paths = tuple(item.path for item in items)
            grouped_paths.update(paths)
            action_counts: dict[str, int] = {}
            for item in items:
                action_counts[item.action.value] = action_counts.get(item.action.value, 0) + 1
            summary = ", ".join(f"{name}={count}" for name, count in sorted(action_counts.items()))
            groups.append(DecisionGroup(label.lower(), kind, len(paths), True, f"{label} batch: {summary}", paths))

    remaining = tuple(item.path for item in plan.items if item.approval_required and item.path not in grouped_paths)
    if remaining:
        groups.append(DecisionGroup("other", DecisionGroupKind.OTHER, len(remaining), True, f"{len(remaining)} remaining approval items outside grouped inboxes", remaining))

    return tuple(groups)


def render_decision_groups(groups: tuple[DecisionGroup, ...]) -> str:
    lines = ["DECISION GROUPS:"]
    for index, group in enumerate(groups, 1):
        lines.append(f"  {index:02d}. [{group.kind.value}] {group.item_count} items")
        lines.append(f"      {group.summary}")
    lines.append(f"DECISION_GROUPS = {len(groups)}")
    return "\n".join(lines)
