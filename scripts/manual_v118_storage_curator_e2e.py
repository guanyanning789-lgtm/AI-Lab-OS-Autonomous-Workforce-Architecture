from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.storage_cleanup_plan import CleanupAction, CleanupItem
from ai_lab_os.storage_executor import StorageApproval, execute_cleanup_item
from ai_lab_os.storage_rollback import create_transaction, rollback_transaction
from ai_lab_os.storage_verifier import verify_execution


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    print("=" * 78)
    print("STORAGE CURATOR V1.1.8 REAL LOCAL E2E")
    print("=" * 78)
    print("SCOPE  = temporary test directory only")
    print("SAFETY = no real Downloads / Models / Projects are touched")
    print()

    with tempfile.TemporaryDirectory(prefix="storage-curator-v118-") as temporary:
        root = Path(temporary)
        inbox = root / "Inbox"
        quarantine = root / "Quarantine"
        inbox.mkdir()

        source = inbox / "old.tmp"
        source.write_bytes(b"storage-curator-e2e-payload")
        expected_hash = sha256(source)
        print(f"SOURCE = {source}")
        print(f"SHA256 = {expected_hash}")

        item = CleanupItem(
            path=str(source),
            action=CleanupAction.CLEAN,
            bytes_affected=source.stat().st_size,
            approval_required=True,
            reason="V1.1.8 isolated cleanup candidate",
        )

        denied = execute_cleanup_item(
            item,
            StorageApproval(str(source), CleanupAction.CLEAN, False),
            quarantine_root=quarantine,
        )
        print(f"DENIED_WITHOUT_APPROVAL = {not denied.ok}")
        if denied.ok or not source.exists():
            print("RESULT = FAILED")
            print("ERROR  = execution occurred without approval")
            return 1

        executed = execute_cleanup_item(
            item,
            StorageApproval(str(source), CleanupAction.CLEAN, True),
            quarantine_root=quarantine,
        )
        print(f"EXECUTED = {executed.ok}")
        if not executed.ok or not executed.quarantine_path:
            print("RESULT = FAILED")
            print(f"ERROR  = {executed.message}")
            return 1

        verified = verify_execution(executed, expected_sha256=expected_hash)
        print(f"VERIFIED = {verified.ok}")
        if not verified.ok:
            print("RESULT = FAILED")
            print("ERROR  = post-action verification failed")
            return 1

        transaction = create_transaction(
            transaction_id="v118-e2e",
            action=CleanupAction.CLEAN,
            source=source,
            destination=Path(executed.quarantine_path),
        )
        rolled_back = rollback_transaction(transaction)
        print(f"ROLLBACK = {rolled_back.ok}")
        if not rolled_back.ok:
            print("RESULT = FAILED")
            print(f"ERROR  = {rolled_back.message}")
            return 1

        if not source.exists() or sha256(source) != expected_hash:
            print("RESULT = FAILED")
            print("ERROR  = rollback did not restore exact original bytes")
            return 1

        quarantine_path = Path(executed.quarantine_path)
        if quarantine_path.exists():
            print("RESULT = FAILED")
            print("ERROR  = quarantine copy still exists after rollback")
            return 1

        print("GOAL_COMPLETE")
        print("RESULT = DONE")
        print("MESSAGE = Storage Curator isolated E2E passed approval, quarantine, SHA256 verification and rollback without touching real user files.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
