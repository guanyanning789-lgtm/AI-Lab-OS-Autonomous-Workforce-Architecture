from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupItem
from ai_lab_os.storage_decision_groups import DecisionGroup


@dataclass(frozen=True)
class StorageSubgroup:
    parent_key: str
    key: str
    label: str
    item_count: int
    total_bytes: int
    paths: tuple[str, ...]


_CATEGORY_SUFFIXES = {
    "images": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"},
    "video": {".mp4", ".mov", ".mkv", ".webm", ".avi"},
    "documents": {".pdf", ".txt", ".md", ".docx", ".xlsx", ".pptx"},
    "archives": {".zip", ".7z", ".rar", ".tar", ".gz"},
    "models": {".safetensors", ".gguf", ".ckpt", ".pt", ".pth"},
}


def _category(path: str) -> str:
    suffix = Path(path).suffix.lower()
    for category, suffixes in _CATEGORY_SUFFIXES.items():
        if suffix in suffixes:
            return category
    return "other"


def build_subgroups(group: DecisionGroup, cleanup_items: tuple[CleanupItem, ...]) -> tuple[StorageSubgroup, ...]:
    item_by_path = {item.path: item for item in cleanup_items}
    buckets: dict[str, list[str]] = {}
    for path in group.paths:
        item = item_by_path.get(path)
        category = _category(path)
        action = item.action.value if item else "unknown"
        key = f"{category}:{action}"
        buckets.setdefault(key, []).append(path)

    output: list[StorageSubgroup] = []
    for key, paths in sorted(buckets.items()):
        category, action = key.split(":", 1)
        total = sum(item_by_path[path].bytes_affected for path in paths if path in item_by_path)
        output.append(StorageSubgroup(group.key, key, f"{category} / {action}", len(paths), total, tuple(paths)))
    return tuple(output)


def render_subgroups(group: DecisionGroup, subgroups: tuple[StorageSubgroup, ...], *, max_examples: int = 3) -> str:
    lines = [f"SUBGROUPS: {group.key}"]
    for index, subgroup in enumerate(subgroups, 1):
        lines.append(f"  {index:02d}. {subgroup.label}: {subgroup.item_count} items, {subgroup.total_bytes / (1024 ** 3):.3f} GB")
        for path in subgroup.paths[:max_examples]:
            lines.append(f"      - {path}")
        if len(subgroup.paths) > max_examples:
            lines.append(f"      ... {len(subgroup.paths) - max_examples} more")
    lines.append(f"SUBGROUP_COUNT = {len(subgroups)}")
    return "\n".join(lines)
