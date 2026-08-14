from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction, CleanupItem
from ai_lab_os.storage_executor import StorageApproval, StorageExecutionResult, execute_cleanup_item


@dataclass(frozen=True)
class ExactContractItem:
    source: str
    destination: str
    action: str
    sha256: str


@dataclass(frozen=True)
class ExactContract:
    items: tuple[ExactContractItem, ...]
    digest: str


def contract_digest(items: tuple[ExactContractItem, ...]) -> str:
    payload = [
        {"source": item.source, "destination": item.destination, "action": item.action, "sha256": item.sha256}
        for item in items
    ]
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_exact_contract(items: tuple[ExactContractItem, ...]) -> ExactContract:
    return ExactContract(items=items, digest=contract_digest(items))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_exact_contract(contract: ExactContract, approval_digest: str | None) -> tuple[bool, str]:
    if not approval_digest or approval_digest != contract.digest:
        return False, "exact approval digest missing or mismatched"
    for item in contract.items:
        if item.action != "migrate":
            return False, f"unsupported action in exact contract: {item.action}"
        source = Path(item.source)
        destination = Path(item.destination)
        if not source.exists() or not source.is_file():
            return False, f"source missing: {source}"
        if destination.exists():
            return False, f"destination already exists: {destination}"
        if _sha256(source) != item.sha256:
            return False, f"source hash changed: {source}"
    return True, "exact approval contract validated"


def execute_exact_contract(
    contract: ExactContract,
    approval_digest: str | None,
    *,
    quarantine_root: Path,
) -> tuple[StorageExecutionResult, ...]:
    valid, reason = validate_exact_contract(contract, approval_digest)
    if not valid:
        raise ValueError(reason)

    results: list[StorageExecutionResult] = []
    for item in contract.items:
        source = Path(item.source)
        cleanup = CleanupItem(
            path=item.source,
            action=CleanupAction.MIGRATE,
            bytes_affected=source.stat().st_size,
            approval_required=True,
            reason="exact contract approved migration",
            destination=item.destination,
        )
        result = execute_cleanup_item(
            cleanup,
            StorageApproval(item.source, CleanupAction.MIGRATE, True),
            quarantine_root=quarantine_root,
        )
        results.append(result)
        if not result.ok:
            break
    return tuple(results)
