from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.storage_cleanup_plan import build_cleanup_plan, render_cleanup_plan
from ai_lab_os.storage_collision_guard import guard_plan
from ai_lab_os.storage_curator import build_storage_plan
from ai_lab_os.storage_path_planner import build_migration_plan


def existing_user_roots() -> tuple[Path, ...]:
    home = Path.home()
    candidates = (
        home / "Downloads",
        home / "Desktop",
        Path(r"C:\AI-Lab"),
        Path(r"D:\AI-Lab"),
    )
    seen: set[str] = set()
    roots: list[Path] = []
    for path in candidates:
        key = os.path.normcase(str(path.resolve())) if path.exists() else os.path.normcase(str(path))
        if path.exists() and key not in seen:
            seen.add(key)
            roots.append(path)
    return tuple(roots)


def main() -> int:
    parser = argparse.ArgumentParser(description="Storage Curator V1.2 real read-only preview")
    parser.add_argument("--max-files", type=int, default=100000)
    parser.add_argument("--duplicate-min-mb", type=int, default=100)
    parser.add_argument("--max-items", type=int, default=40)
    args = parser.parse_args()

    roots = existing_user_roots()
    print("=" * 78)
    print("STORAGE CURATOR V1.2 REAL STORAGE PREVIEW")
    print("=" * 78)
    print("MODE   = READ ONLY")
    print("SAFETY = no delete, move, rename, quarantine or write operations")
    print("ROOTS:")
    for root in roots:
        print(f"  {root}")
    print()

    if not roots:
        print("RESULT = FAILED")
        print("ERROR  = no configured preview roots exist")
        return 1

    storage = build_storage_plan(
        roots,
        max_files=max(1, args.max_files),
        duplicate_min_bytes=max(1, args.duplicate_min_mb) * 1024 * 1024,
    )
    proposals = build_migration_plan(storage.candidates)
    guards = guard_plan(proposals)
    cleanup = build_cleanup_plan(storage, guards)

    print(render_cleanup_plan(cleanup, max_items=max(1, args.max_items)))
    print()
    print(f"SCANNED_FILES = {storage.scanned_files}")
    print(f"TRUNCATED     = {storage.truncated}")
    print("EXECUTED      = False")
    print("RESULT        = PREVIEW_ONLY")
    print("MESSAGE       = Review this plan before any real Storage Curator approval/execution stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
