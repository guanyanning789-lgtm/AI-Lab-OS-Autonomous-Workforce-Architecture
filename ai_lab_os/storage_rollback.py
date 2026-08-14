from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ai_lab_os.storage_cleanup_plan import CleanupAction


@dataclass(frozen=True)
class StorageTransaction:
    transaction_id: str
    action: CleanupAction
    source: str
    destination: str
    sha256: str
    created_at: float


@dataclass(frozen=True)
class RollbackResult:
    ok: bool
    transaction_id: str
    restored_path: str | None
    message: str


class StorageTransactionLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, transaction: StorageTransaction) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**asdict(transaction), "action": transaction.action.value}, ensure_ascii=False) + "\n")

    def load(self, transaction_id: str) -> StorageTransaction:
        if not self.path.exists():
            raise LookupError(transaction_id)
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                data = json.loads(line)
                if data.get("transaction_id") == transaction_id:
                    return StorageTransaction(
                        transaction_id=data["transaction_id"],
                        action=CleanupAction(data["action"]),
                        source=data["source"],
                        destination=data["destination"],
                        sha256=data["sha256"],
                        created_at=float(data["created_at"]),
                    )
        raise LookupError(transaction_id)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def create_transaction(*, transaction_id: str, action: CleanupAction, source: Path, destination: Path) -> StorageTransaction:
    if not destination.exists() or not destination.is_file():
        raise ValueError("destination must exist before recording transaction")
    return StorageTransaction(transaction_id, action, str(source), str(destination), _sha256(destination), time.time())


def rollback_transaction(transaction: StorageTransaction) -> RollbackResult:
    source = Path(transaction.source)
    destination = Path(transaction.destination)

    if source.exists():
        return RollbackResult(False, transaction.transaction_id, None, "original source path is occupied; rollback blocked")
    if not destination.exists() or not destination.is_file():
        return RollbackResult(False, transaction.transaction_id, None, "transaction destination is missing")
    try:
        if _sha256(destination) != transaction.sha256:
            return RollbackResult(False, transaction.transaction_id, None, "destination content changed after execution; rollback blocked")
    except OSError:
        return RollbackResult(False, transaction.transaction_id, None, "cannot verify destination content")

    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(destination), str(source))
    if not source.exists() or _sha256(source) != transaction.sha256:
        return RollbackResult(False, transaction.transaction_id, str(source), "rollback verification failed")
    return RollbackResult(True, transaction.transaction_id, str(source), "rollback completed and SHA256 verified")
