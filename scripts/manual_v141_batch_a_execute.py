from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.storage_cleanup_plan import CleanupAction
from ai_lab_os.storage_exact_executor import ExactContractItem, build_exact_contract, execute_exact_contract
from ai_lab_os.storage_rollback import StorageTransactionLedger, create_transaction
from ai_lab_os.storage_verifier import verify_batch

EXPECTED_DIGEST = "e5bce66516be98ae95c78d6ac6d32ffc9af458260018461d41357710534c3553"
ITEMS = (
    (r"C:\Users\PC\Downloads\ChatGPT Image 2026年8月14日 17_59_38.png", r"D:\AI-Lab\Media\Images\ChatGPT Image 2026年8月14日 17_59_38.png", "b48b7b0264ac933185d3ce87c4385c9b083ff324dda4e176fb0140b8f4acc290"),
    (r"C:\Users\PC\Downloads\Mobile Devices\IMG_8610.PNG", r"D:\AI-Lab\Media\Images\IMG_8610.PNG", "f23dc8d63f5198d411f6916daba02d34df08ac2dbd86bb3d60ed59b04e2f56c5"),
    (r"C:\Users\PC\Desktop\1af335ef-7f1c-4c7d-ad05-dc30857f0b4c.png", r"D:\AI-Lab\Media\Images\1af335ef-7f1c-4c7d-ad05-dc30857f0b4c.png", "9a409c4f6b8a10a7445360c5ad78b2410abc6ee00ac3a92acde1b128c8004f87"),
    (r"C:\Users\PC\Desktop\30bcf35b-f2c9-4661-bc07-dbe6723467a2.png", r"D:\AI-Lab\Media\Images\30bcf35b-f2c9-4661-bc07-dbe6723467a2.png", "c78e5a73164d7d21778e6dc56eaee878892265065ece0265c3e7e57bdda2550a"),
    (r"C:\Users\PC\Desktop\6ad26828-eb8c-4671-8518-2f3a53c524a9.png", r"D:\AI-Lab\Media\Images\6ad26828-eb8c-4671-8518-2f3a53c524a9.png", "0af66801ebac0fa1e228f9728851704c07975d93afa3ca0cfc213a703c10f8e2"),
    (r"C:\Users\PC\Desktop\coe.png", r"D:\AI-Lab\Media\Images\coe.png", "6b6186226f140208ba76cb6fe051047e82fdadbbab57625040c8df42087e155f"),
    (r"C:\Users\PC\Desktop\任務調度中心.png", r"D:\AI-Lab\Media\Images\任務調度中心.png", "e0b0d711bfea0c96a19629a664fbc66bf752aaa08b8d42e553dd97c8f959ce79"),
    (r"C:\Users\PC\Desktop\内容創作.png", r"D:\AI-Lab\Media\Images\内容創作.png", "112f36b67b9b0cfb3d1d5dc481af91e5f40d9df5420612ba5896126cdda6319f"),
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024): h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval-digest", required=True)
    args = parser.parse_args()
    contract = build_exact_contract(tuple(ExactContractItem(s, d, "migrate", h) for s, d, h in ITEMS))
    print("=" * 78); print("STORAGE CURATOR V1.4.1 BATCH A REAL EXECUTION"); print("=" * 78)
    print(f"CONTRACT_DIGEST = {contract.digest}"); print(f"EXPECTED_DIGEST = {EXPECTED_DIGEST}")
    if contract.digest != EXPECTED_DIGEST or args.approval_digest != EXPECTED_DIGEST:
        print("RESULT = BLOCKED"); return 2
    results = execute_exact_contract(contract, args.approval_digest, quarantine_root=Path(r"D:\AI-Lab\Quarantine"))
    for i, result in enumerate(results, 1): print(f"MOVE_{i} = {result.ok} :: {result.source} -> {result.destination}")
    batch = verify_batch(results)
    print(f"VERIFIED = {batch.ok}"); print(f"VERIFIED_ITEMS = {batch.verified}"); print(f"FAILED_ITEMS = {batch.failed}")
    if not batch.ok or len(results) != len(ITEMS): print("RESULT = FAILED"); return 1
    ledger = StorageTransactionLedger(Path(r"D:\AI-Lab\StorageCurator\transactions.jsonl"))
    for i, (source, destination, expected_hash) in enumerate(ITEMS, 1):
        dest = Path(destination)
        if sha256(dest) != expected_hash: print("RESULT = FAILED"); return 1
        tx = create_transaction(transaction_id=f"v141-batch-a-{i}", action=CleanupAction.MIGRATE, source=Path(source), destination=dest)
        ledger.append(tx)
    print(f"TRANSACTIONS = {len(ITEMS)}"); print("ROLLBACK_READY = True"); print("GOAL_COMPLETE"); print("RESULT = DONE")
    print("MESSAGE = Exactly eight approved images moved and verified; no other files were authorized.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
