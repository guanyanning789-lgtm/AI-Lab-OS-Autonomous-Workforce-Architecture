from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_migration_blueprint import MigrationBlueprintItem


@dataclass(frozen=True)
class SubgroupContractItem:
    source: str
    destination: str
    sha256: str
    action: str = "migrate"
    risk: str = "LOW"


@dataclass(frozen=True)
class SubgroupContract:
    items: tuple[SubgroupContractItem, ...]
    digest: str
    executable: bool = False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(items: tuple[SubgroupContractItem, ...]) -> str:
    payload = [
        {"source": i.source, "destination": i.destination, "sha256": i.sha256, "action": i.action, "risk": i.risk}
        for i in items
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_low_risk_subgroup_contract(
    blueprint: tuple[MigrationBlueprintItem, ...],
    *,
    limit: int = 15,
) -> SubgroupContract:
    selected: list[SubgroupContractItem] = []
    allowed_suffixes = {".pdf", ".png", ".jpg", ".jpeg"}
    for item in blueprint:
        source = Path(item.source)
        destination = Path(item.destination)
        parts = {part.lower() for part in source.parts}
        if item.risk != "LOW" or not item.rollback_ready:
            continue
        if not ({"desktop", "downloads"} & parts):
            continue
        if source.suffix.lower() not in allowed_suffixes:
            continue
        if not source.exists() or not source.is_file() or destination.exists():
            continue
        selected.append(SubgroupContractItem(str(source), str(destination), _sha256(source)))
        if len(selected) >= max(1, min(limit, 20)):
            break
    frozen = tuple(selected)
    return SubgroupContract(frozen, _digest(frozen), False)


def render_subgroup_contract(contract: SubgroupContract) -> str:
    lines = ["LOW-RISK SUBGROUP CONTRACT (PREVIEW ONLY)"]
    for index, item in enumerate(contract.items, 1):
        lines.extend([
            f"  {index:02d}. source      = {item.source}",
            f"      destination = {item.destination}",
            f"      sha256      = {item.sha256}",
            f"      action      = {item.action}",
            f"      risk        = {item.risk}",
        ])
    lines.append(f"SUBGROUP_ITEMS = {len(contract.items)}")
    lines.append(f"CONTRACT_DIGEST = {contract.digest}")
    lines.append("APPROVED = False")
    lines.append("EXECUTABLE = False")
    return "\n".join(lines)
