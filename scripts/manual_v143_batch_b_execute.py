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

EXPECTED_DIGEST = "a80b8b069eebf169db7035fba00afc2dcb1e7f12825ad58ddd70b3eb682de7de"
ITEMS = (
    (r"C:\Users\PC\Desktop\學習計劃.png", r"D:\AI-Lab\Media\Images\學習計劃.png", "de41bca1842bed702fac9efd2fcaa751721aa6f5cb8de3ba18ab592699e0573e"),
    (r"C:\Users\PC\Desktop\文件管理員.png", r"D:\AI-Lab\Media\Images\文件管理員.png", "98997461b7ee0ecca8c0e8e904ee6738301c55ccae0d411b52a5574974f5672f"),
    (r"C:\Users\PC\Desktop\瀏覽器專家.png", r"D:\AI-Lab\Media\Images\瀏覽器專家.png", "9cdf30352f6266f3522c28daf4a0c7dcedaf1000399ab2b446b6502b1fa7b157"),
    (r"C:\Users\PC\Desktop\生活管理.png", r"D:\AI-Lab\Media\Images\生活管理.png", "5976000259441abce2c66324baf789a366a948ee4f371b86666c768ac05feb27"),
    (r"C:\Users\PC\Desktop\知識管理員.png", r"D:\AI-Lab\Media\Images\知識管理員.png", "b18c97a0558b5b83beaf289efe8e8bb7e07588fa28803d541c895155dfb20a9e"),
    (r"C:\Users\PC\Desktop\研究分析.png", r"D:\AI-Lab\Media\Images\研究分析.png", "f5bcd74ffafe5ebe33d7fb937e84ea7785cf5a8988fe1ea6673a8bc57e524c5b"),
    (r"C:\Users\PC\Desktop\系統操作員.png", r"D:\AI-Lab\Media\Images\系統操作員.png", "054e0346d901d4153a8befe5cd9d842f31b3c64299d1310dac8c82a943e8669b"),
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
    print("=" * 78); print("STORAGE CURATOR V1.4.3 BATCH B REAL EXECUTION"); print("=" * 78)
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
        ledger.append(create_transaction(transaction_id=f"v143-batch-b-{i}", action=CleanupAction.MIGRATE, source=Path(source), destination=dest))
    print(f"TRANSACTIONS = {len(ITEMS)}"); print("ROLLBACK_READY = True"); print("GOAL_COMPLETE"); print("RESULT = DONE")
    print("MESSAGE = Exactly seven approved Batch B images moved and verified; no other files were authorized.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
