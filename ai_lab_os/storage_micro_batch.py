from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_migration_blueprint import MigrationBlueprintItem


@dataclass(frozen=True)
class MicroBatch:
    items: tuple[MigrationBlueprintItem, ...]
    executable: bool
    reason: str


def select_micro_batch(
    blueprint: tuple[MigrationBlueprintItem, ...],
    *,
    limit: int = 5,
) -> MicroBatch:
    selected: list[MigrationBlueprintItem] = []
    for item in blueprint:
        source = Path(item.source)
        destination = Path(item.destination)
        lowered = {part.lower() for part in source.parts}
        if item.risk != "LOW" or not item.rollback_ready:
            continue
        if not ({"desktop", "downloads"} & lowered):
            continue
        if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".pdf", ".txt", ".mp4", ".zip"}:
            continue
        if destination.exists():
            continue
        selected.append(item)
        if len(selected) >= max(1, limit):
            break
    return MicroBatch(tuple(selected), False, "preview selection only; exact explicit approval is required before execution")


def render_micro_batch(batch: MicroBatch) -> str:
    lines = ["FIRST MICRO-BATCH CANDIDATES (NOT EXECUTED)"]
    for index, item in enumerate(batch.items, 1):
        lines.append(f"  {index}. {item.source}")
        lines.append(f"     -> {item.destination}")
        lines.append(f"     risk={item.risk} rollback=YES")
    lines.append(f"MICRO_BATCH_ITEMS = {len(batch.items)}")
    lines.append("APPROVED = False")
    lines.append("EXECUTABLE = False")
    lines.append(f"REASON = {batch.reason}")
    return "\n".join(lines)
