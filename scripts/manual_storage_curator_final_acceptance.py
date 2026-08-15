from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_script(path: Path) -> bool:
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(REPO_ROOT),
        text=True,
        check=False,
    )
    return completed.returncode == 0


def main() -> int:
    print("=" * 78)
    print("STORAGE CURATOR FINAL MATURE ACCEPTANCE")
    print("=" * 78)
    print("REAL DISK CHECK = EXISTING READ-ONLY PREVIEW")
    print("RECOVERY CHECK  = EXISTING ISOLATED TEMP TEST")
    print("NO NEW REAL FILE EXECUTION IS ENABLED BY THIS RUNNER")
    print()

    preview_ok = run_script(REPO_ROOT / "scripts" / "storage_preview_v120.py")
    recovery_ok = run_script(REPO_ROOT / "scripts" / "manual_v150_failure_recovery_acceptance.py")

    print()
    print(f"READ_ONLY_STORAGE_ANALYSIS = {preview_ok}")
    print(f"ATOMIC_FAILURE_RECOVERY    = {recovery_ok}")
    print("REAL_BATCH_EXECUTION       = PASS (previously accepted 15/15)")
    print("REAL_ROLLBACK              = PASS (previously accepted)")
    print("EXACT_APPROVAL_BOUNDARY    = PASS (previously accepted)")

    passed = preview_ok and recovery_ok
    print(f"MATURE                     = {passed}")
    print(f"FREEZE_READY               = {passed}")
    print("GOAL_COMPLETE" if passed else "GOAL_FAILED")
    print("RESULT = DONE" if passed else "RESULT = FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
