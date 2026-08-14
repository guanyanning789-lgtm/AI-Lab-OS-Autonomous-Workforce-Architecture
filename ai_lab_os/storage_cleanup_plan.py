from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_lab_os.storage_collision_guard import GuardDecision, GuardResult
from ai_lab_os.storage_curator import StorageDisposition, StoragePlan


class CleanupAction(str, Enum):
    KEEP = "keep"
    REVIEW = "review"
    ARCHIVE = "archive"
    DELETE_DUPLICATE = "delete_duplicate"
    CLEAN = "clean"
    MIGRATE = "migrate"
    BLOCK = "block"


@dataclass(frozen=True)
class CleanupItem:
    path: str
    action: CleanupAction
    bytes_affected: int
    approval_required: bool
    reason: str
    destination: str | None = None


@dataclass(frozen=True)
class CleanupPlan:
    items: tuple[CleanupItem, ...]
    estimated_reclaimable_bytes: int
    duplicate_groups: int
    approval_items: int
    blocked_items: int
    truncated_scan: bool


def build_cleanup_plan(storage: StoragePlan, guards: tuple[GuardResult, ...] = ()) -> CleanupPlan:
    guard_by_source = {item.proposal.source: item for item in guards}
    items: list[CleanupItem] = []

    for candidate in storage.candidates:
        guard = guard_by_source.get(candidate.path)
        if candidate.disposition is StorageDisposition.PROTECTED:
            items.append(CleanupItem(candidate.path, CleanupAction.BLOCK, 0, False, candidate.reason))
        elif candidate.disposition is StorageDisposition.DUPLICATE:
            items.append(CleanupItem(candidate.path, CleanupAction.DELETE_DUPLICATE, candidate.size, True, candidate.reason))
        elif candidate.disposition is StorageDisposition.CLEAN_CANDIDATE:
            items.append(CleanupItem(candidate.path, CleanupAction.CLEAN, candidate.size, True, candidate.reason))
        elif candidate.disposition is StorageDisposition.ARCHIVE:
            destination = guard.proposal.destination if guard else None
            items.append(CleanupItem(candidate.path, CleanupAction.ARCHIVE, 0, True, candidate.reason, destination))
        elif candidate.disposition is StorageDisposition.REVIEW:
            destination = guard.proposal.destination if guard else None
            items.append(CleanupItem(candidate.path, CleanupAction.REVIEW, 0, True, candidate.reason, destination))
        elif guard and guard.decision is GuardDecision.SAFE_TO_PLAN:
            items.append(CleanupItem(candidate.path, CleanupAction.MIGRATE, 0, True, guard.reason, guard.proposal.destination))
        elif guard and guard.decision in {GuardDecision.COLLISION, GuardDecision.REFERENCE_RISK, GuardDecision.BLOCKED}:
            items.append(CleanupItem(candidate.path, CleanupAction.BLOCK, 0, False, guard.reason, guard.proposal.destination))
        else:
            items.append(CleanupItem(candidate.path, CleanupAction.KEEP, 0, False, candidate.reason))

    reclaimable = sum(item.bytes_affected for item in items if item.action in {CleanupAction.DELETE_DUPLICATE, CleanupAction.CLEAN})
    return CleanupPlan(
        items=tuple(items),
        estimated_reclaimable_bytes=reclaimable,
        duplicate_groups=len(storage.duplicates),
        approval_items=sum(1 for item in items if item.approval_required),
        blocked_items=sum(1 for item in items if item.action is CleanupAction.BLOCK),
        truncated_scan=storage.truncated,
    )


def render_cleanup_plan(plan: CleanupPlan, *, max_items: int = 30) -> str:
    gb = plan.estimated_reclaimable_bytes / (1024 ** 3)
    lines = [
        "STORAGE CURATOR CLEANUP PLAN (NO CHANGES EXECUTED)",
        f"ESTIMATED RECLAIMABLE = {gb:.1f} GB",
        f"DUPLICATE GROUPS      = {plan.duplicate_groups}",
        f"APPROVAL ITEMS        = {plan.approval_items}",
        f"BLOCKED ITEMS         = {plan.blocked_items}",
        f"SCAN                  = {'PARTIAL' if plan.truncated_scan else 'COMPLETE'}",
        "",
    ]
    priority = {CleanupAction.CLEAN: 0, CleanupAction.DELETE_DUPLICATE: 1, CleanupAction.MIGRATE: 2, CleanupAction.ARCHIVE: 3, CleanupAction.REVIEW: 4, CleanupAction.BLOCK: 5, CleanupAction.KEEP: 6}
    selected = sorted(plan.items, key=lambda item: (priority[item.action], -item.bytes_affected))[:max_items]
    for item in selected:
        size_gb = item.bytes_affected / (1024 ** 3)
        destination = f" -> {item.destination}" if item.destination else ""
        approval = " APPROVAL" if item.approval_required else ""
        lines.append(f"[{item.action.value.upper()}]{approval} {size_gb:.2f} GB {item.path}{destination}")
        lines.append(f"  {item.reason}")
    return "\n".join(lines)
