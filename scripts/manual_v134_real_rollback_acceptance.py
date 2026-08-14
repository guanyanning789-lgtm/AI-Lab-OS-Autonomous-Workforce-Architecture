from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.storage_cleanup_plan import CleanupAction
from ai_lab_os.storage_rollback import create_transaction, rollback_transaction

SOURCE = Path(r"C:\Users\PC\Downloads\AI Lab 總需求清單.pdf")
DESTINATION = Path(r"D:\Knowledge\Documents\AI Lab 總需求清單.pdf")
EXPECTED_SHA256 = "7caadeb16822764a4f2235799d983a2a8f4e5f9ea1c0fe9cda46a22479f36e9f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    print("=" * 78)
    print("STORAGE CURATOR V1.3.4 REAL ROLLBACK ACCEPTANCE")
    print("=" * 78)
    print(f"SOURCE      = {SOURCE}")
    print(f"DESTINATION = {DESTINATION}")
    print("SCOPE       = exactly one previously approved PDF")
    print()

    if SOURCE.exists():
        print("RESULT = BLOCKED")
        print("ERROR  = original source path is already occupied")
        return 1
    if not DESTINATION.exists() or not DESTINATION.is_file():
        print("RESULT = BLOCKED")
        print("ERROR  = migrated destination is missing")
        return 1
    if sha256(DESTINATION) != EXPECTED_SHA256:
        print("RESULT = BLOCKED")
        print("ERROR  = destination SHA256 changed")
        return 1

    transaction = create_transaction(
        transaction_id="v134-real-rollback",
        action=CleanupAction.MIGRATE,
        source=SOURCE,
        destination=DESTINATION,
    )
    rollback = rollback_transaction(transaction)
    print(f"ROLLBACK = {rollback.ok}")
    if not rollback.ok:
        print("RESULT = FAILED")
        print(f"ERROR  = {rollback.message}")
        return 1

    if not SOURCE.exists() or sha256(SOURCE) != EXPECTED_SHA256:
        print("RESULT = FAILED")
        print("ERROR  = restored source verification failed")
        return 1
    print("RESTORE_VERIFIED = True")

    if DESTINATION.exists():
        print("RESULT = FAILED")
        print("ERROR  = destination still exists after rollback")
        return 1

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(SOURCE), str(DESTINATION))
    if SOURCE.exists() or not DESTINATION.exists() or sha256(DESTINATION) != EXPECTED_SHA256:
        print("RESULT = FAILED")
        print("ERROR  = re-migration verification failed")
        return 1

    print("REMIGRATED = True")
    print("FINAL_SHA256_VERIFIED = True")
    print("GOAL_COMPLETE")
    print("RESULT = DONE")
    print("MESSAGE = One approved PDF was rolled back to Downloads, SHA256 verified, then safely re-migrated to D:\\Knowledge\\Documents and verified again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
