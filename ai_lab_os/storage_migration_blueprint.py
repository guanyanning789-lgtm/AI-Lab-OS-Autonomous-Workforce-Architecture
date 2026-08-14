from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction, CleanupItem


@dataclass(frozen=True)
class MigrationBlueprintItem:
    source: str
    destination: str
    action: CleanupAction
    risk: str
    rollback_ready: bool
    reason: str


def _risk(item: CleanupItem) -> str:
    source = Path(item.path)
    lowered = {part.lower() for part in source.parts}
    if item.action is CleanupAction.REVIEW:
        return "HIGH"
    if "desktop" in lowered or "downloads" in lowered:
        return "LOW"
    return "MEDIUM"


def build_migration_blueprint(items: tuple[CleanupItem, ...]) -> tuple[MigrationBlueprintItem, ...]:
    output: list[MigrationBlueprintItem] = []
    for item in items:
        if item.action not in {CleanupAction.MIGRATE, CleanupAction.ARCHIVE}:
            continue
        if not item.destination:
            continue
        output.append(
            MigrationBlueprintItem(
                source=item.path,
                destination=item.destination,
                action=item.action,
                risk=_risk(item),
                rollback_ready=True,
                reason="canonical destination proposal; collision guard and explicit approval still required",
            )
        )
    return tuple(output)


def render_migration_blueprint(items: tuple[MigrationBlueprintItem, ...], *, max_items: int = 30) -> str:
    lines = ["CANONICAL MIGRATION BLUEPRINT (PREVIEW ONLY)"]
    for index, item in enumerate(items[:max_items], 1):
        lines.extend([
            f"  {index:02d}. {item.source}",
            f"      -> {item.destination}",
            f"      action={item.action.value} risk={item.risk} rollback={'YES' if item.rollback_ready else 'NO'}",
            f"      reason={item.reason}",
        ])
    if len(items) > max_items:
        lines.append(f"  ... {len(items) - max_items} more migration candidates")
    lines.append(f"MIGRATION_BLUEPRINT_ITEMS = {len(items)}")
    return "\n".join(lines)
