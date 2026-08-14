from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.storage_cleanup_plan import CleanupAction
from ai_lab_os.storage_exact_executor import ExactContractItem, build_exact_contract, execute_exact_contract
from ai_lab_os.storage_rollback import create_transaction
from ai_lab_os.storage_verifier import verify_batch

EXPECTED_DIGEST = "1f1e74cca8c4809400dd11ece8741330a6362fa9188ab35afca67f00ccff70c6"

ITEMS = (
    ExactContractItem(
        source=r"C:\Users\PC\Downloads\AI Lab 總需求清單.pdf",
        destination=r"D:\Knowledge\Documents\AI Lab 總需求清單.pdf",
        action="migrate",
        sha256="7caadeb16822764a4f2235799d983a2a8f4e5f9ea1c0fe9cda46a22479f36e9f",
    ),
    ExactContractItem(
        source=r"C:\Users\PC\Downloads\AI_Lab_Agent_OS_Architecture.pdf",
        destination=r"D:\Knowledge\Documents\AI_Lab_Agent_OS_Architecture.pdf",
        action="migrate",
        sha256="0f8f474beaeb49f9495c922425dcf88100a84a0086a1669e97b79c204d3dde6a",
    ),
    ExactContractItem(
        source=r"C:\Users\PC\Downloads\AI_Lab_总需求清单_黑白极简版.pdf",
        destination=r"D:\Knowledge\Documents\AI_Lab_总需求清单_黑白极简版.pdf",
        action="migrate",
        sha256="442d7a46556a44eb0db8f82374cfb8f8d9a6e3b6748eb4c3d9a6d066fd6bad25",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Storage Curator V1.3.3 first real approved micro-batch")
    parser.add_argument("--approval-digest", required=True)
    args = parser.parse_args()

    contract = build_exact_contract(ITEMS)
    print("=" * 78)
    print("STORAGE CURATOR V1.3.3 FIRST REAL 3-FILE MOVE")
    print("=" * 78)
    print(f"CONTRACT_DIGEST = {contract.digest}")
    print(f"EXPECTED_DIGEST = {EXPECTED_DIGEST}")
    print("ITEMS = 3")

    if contract.digest != EXPECTED_DIGEST:
        print("RESULT = BLOCKED")
        print("ERROR  = embedded contract digest drifted")
        return 2
    if args.approval_digest != EXPECTED_DIGEST:
        print("RESULT = BLOCKED")
        print("ERROR  = approval digest mismatch")
        return 3

    quarantine = Path(r"D:\AI-Lab\Quarantine\storage-curator-v133")
    try:
        results = execute_exact_contract(contract, args.approval_digest, quarantine_root=quarantine)
    except ValueError as exc:
        print("RESULT = BLOCKED")
        print(f"ERROR  = {exc}")
        return 4

    for index, result in enumerate(results, 1):
        print(f"MOVE_{index} = {result.ok} :: {result.source} -> {result.destination}")
        if not result.ok:
            print(f"ERROR_{index} = {result.message}")

    verification = verify_batch(results)
    print(f"VERIFIED = {verification.ok}")
    print(f"VERIFIED_ITEMS = {verification.verified}")
    print(f"FAILED_ITEMS   = {verification.failed}")

    if not verification.ok or len(results) != len(ITEMS):
        print("RESULT = FAILED")
        print("MESSAGE = Do not continue; one or more approved moves failed verification.")
        return 5

    transactions = []
    for index, item in enumerate(ITEMS, 1):
        transactions.append(
            create_transaction(
                transaction_id=f"v133-pdf-{index}",
                action=CleanupAction.MIGRATE,
                source=Path(item.source),
                destination=Path(item.destination),
            )
        )
    print(f"TRANSACTIONS = {len(transactions)}")
    print("ROLLBACK_READY = True")
    print("GOAL_COMPLETE")
    print("RESULT = DONE")
    print("MESSAGE = Exactly three approved PDFs moved to D:\\Knowledge\\Documents and verified; no other files were touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
