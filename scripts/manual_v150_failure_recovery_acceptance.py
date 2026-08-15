from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.storage_atomic_batch import AtomicMove, execute_atomic_batch


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    print("=" * 78)
    print("STORAGE CURATOR V1.5 FAILURE RECOVERY ACCEPTANCE")
    print("=" * 78)
    print("SCOPE  = isolated temporary directory only")
    print("FAULT  = deliberately injected before item 3")
    print("EXPECT = items 1-2 rollback; items 3-5 untouched; original state restored")
    with tempfile.TemporaryDirectory(prefix="storage-v150-") as tmp:
        root = Path(tmp)
        source = root / "source"
        dest = root / "destination"
        source.mkdir(); dest.mkdir()
        moves = []
        hashes = {}
        for index in range(1, 6):
            path = source / f"item-{index}.bin"
            path.write_bytes(f"atomic-batch-item-{index}".encode())
            digest = sha256(path)
            hashes[index] = digest
            moves.append(AtomicMove(path, dest / path.name, digest))

        def inject(index: int, move: AtomicMove) -> None:
            if index == 3:
                raise RuntimeError("INJECTED_FAILURE_ITEM_3")

        result = execute_atomic_batch(tuple(moves), before_move=inject)
        print(f"BATCH_OK = {result.ok}")
        print(f"FAILED_INDEX = {result.failed_index}")
        print(f"EXECUTED_BEFORE_FAILURE = {result.executed}")
        print(f"ROLLED_BACK = {result.rolled_back}")
        print(f"RESTORED = {result.restored}")

        all_restored = True
        for index in range(1, 6):
            src = source / f"item-{index}.bin"
            dst = dest / f"item-{index}.bin"
            ok = src.is_file() and not dst.exists() and sha256(src) == hashes[index]
            all_restored = all_restored and ok
            print(f"ITEM_{index}_ORIGINAL_STATE = {ok}")

        passed = (
            not result.ok
            and result.failed_index == 3
            and result.executed == 2
            and result.rolled_back == 2
            and result.restored
            and all_restored
        )
        print(f"PARTIAL_FAILURE_DETECTED = {not result.ok}")
        print(f"POST_FAILURE_ITEMS_BLOCKED = {not (dest / 'item-4.bin').exists() and not (dest / 'item-5.bin').exists()}")
        print(f"ALL_SHA256_RESTORED = {all_restored}")
        print("GOAL_COMPLETE" if passed else "GOAL_FAILED")
        print("RESULT = DONE" if passed else "RESULT = FAILED")
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
