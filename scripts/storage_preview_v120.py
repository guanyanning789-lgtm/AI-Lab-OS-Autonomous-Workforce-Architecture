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
from ai_lab_os.storage_curator import StoragePlan, build_storage_plan
from ai_lab_os.storage_decision_groups import build_decision_groups, render_decision_groups
from ai_lab_os.storage_group_detail import render_group_details
from ai_lab_os.storage_intelligence import apply_project_boundaries, build_version_families
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
    parser = argparse.ArgumentParser(description="Storage Curator V1.2.3 real read-only preview")
    parser.add_argument("--max-files", type=int, default=100000)
    parser.add_argument("--duplicate-min-mb", type=int, default=100)
    parser.add_argument("--max-items", type=int, default=25)
    parser.add_argument("--group-examples", type=int, default=5)
    args = parser.parse_args()

    roots = existing_user_roots()
    print("=" * 78)
    print("STORAGE CURATOR V1.2.3 REAL STORAGE PREVIEW")
    print("=" * 78)
    print("MODE   = READ ONLY")
    print("SAFETY = no delete, move, rename, quarantine or write operations")
    print("INTEL  = project boundaries + version families + decision groups + explanations")
    print("ROOTS:")
    for root in roots:
        print(f"  {root}")
    print()

    if not roots:
        print("RESULT = FAILED")
        print("ERROR  = no configured preview roots exist")
        return 1

    raw = build_storage_plan(
        roots,
        max_files=max(1, args.max_files),
        duplicate_min_bytes=max(1, args.duplicate_min_mb) * 1024 * 1024,
    )
    bounded_candidates = apply_project_boundaries(raw.candidates)
    storage = StoragePlan(
        candidates=bounded_candidates,
        duplicates=raw.duplicates,
        reclaimable_bytes=raw.reclaimable_bytes,
        scanned_files=raw.scanned_files,
        truncated=raw.truncated,
    )
    families = build_version_families(bounded_candidates)
    proposals = build_migration_plan(storage.candidates)
    guards = guard_plan(proposals)
    cleanup = build_cleanup_plan(storage, guards)
    groups = build_decision_groups(cleanup, families)

    print(render_cleanup_plan(cleanup, max_items=max(1, args.max_items)))
    print()
    print(render_decision_groups(groups))
    print()
    print(render_group_details(groups, cleanup, max_examples=max(1, args.group_examples)))
    print()
    print("VERSION FAMILIES:")
    if not families:
        print("  none")
    for family in families[:20]:
        print(f"  {family.family}: {len(family.members)} files; latest=v{family.latest.raw_version}")
        print(f"    latest     = {family.latest.path}")
        print(f"    historical = {len(family.historical)}")
    if len(families) > 20:
        print(f"  ... {len(families) - 20} more families")
    print()
    print(f"RAW_APPROVAL_ITEMS = {cleanup.approval_items}")
    print(f"DECISION_GROUPS    = {len(groups)}")
    print(f"VERSION_FAMILIES   = {len(families)}")
    print(f"SCANNED_FILES      = {storage.scanned_files}")
    print(f"TRUNCATED          = {storage.truncated}")
    print("EXECUTED           = False")
    print("RESULT             = PREVIEW_ONLY")
    print("MESSAGE            = Group explanations show size, actions, destinations, risk and rollback readiness before approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
