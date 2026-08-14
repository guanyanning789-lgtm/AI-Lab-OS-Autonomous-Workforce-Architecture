from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.storage_canonical_architecture import render_architecture
from ai_lab_os.storage_cleanup_plan import build_cleanup_plan
from ai_lab_os.storage_collision_guard import guard_plan
from ai_lab_os.storage_curator import StoragePlan, build_storage_plan
from ai_lab_os.storage_decision_groups import build_decision_groups, render_decision_groups
from ai_lab_os.storage_intelligence import apply_project_boundaries, build_version_families
from ai_lab_os.storage_migration_blueprint import build_migration_blueprint
from ai_lab_os.storage_path_planner import build_migration_plan
from ai_lab_os.storage_project_roots import apply_project_root_protection, detect_project_roots
from ai_lab_os.storage_subgroup_contract import build_low_risk_subgroup_contract, render_subgroup_contract
from ai_lab_os.storage_subgroups import build_subgroups


def existing_user_roots() -> tuple[Path, ...]:
    home = Path.home()
    candidates = (home / "Downloads", home / "Desktop", Path(r"C:\AI-Lab"), Path(r"D:\AI-Lab"))
    return tuple(path for path in candidates if path.exists())


def main() -> int:
    parser = argparse.ArgumentParser(description="Storage Curator V1.4 low-risk subgroup preview")
    parser.add_argument("--max-files", type=int, default=100000)
    parser.add_argument("--duplicate-min-mb", type=int, default=100)
    parser.add_argument("--subgroup-items", type=int, default=15)
    args = parser.parse_args()

    roots = existing_user_roots()
    print("=" * 78)
    print("STORAGE CURATOR V1.4.0 LOW-RISK SUBGROUP CONTRACT PREVIEW")
    print("=" * 78)
    print("MODE   = READ ONLY / GROUP CONTRACT PREVIEW")
    print("SAFETY = independent PDF/image candidates only; max 20; no execution")
    if not roots:
        print("RESULT = FAILED")
        return 1

    raw = build_storage_plan(roots, max_files=max(1, args.max_files), duplicate_min_bytes=max(1, args.duplicate_min_mb) * 1024 * 1024)
    bounded = apply_project_boundaries(raw.candidates)
    project_roots = detect_project_roots(bounded)
    protected = apply_project_root_protection(bounded, project_roots)
    storage = StoragePlan(protected, raw.duplicates, raw.reclaimable_bytes, raw.scanned_files, raw.truncated)
    families = build_version_families(protected)
    guards = guard_plan(build_migration_plan(storage.candidates))
    cleanup = build_cleanup_plan(storage, guards)
    groups = build_decision_groups(cleanup, families)
    blueprint = build_migration_blueprint(cleanup.items)
    contract = build_low_risk_subgroup_contract(blueprint, limit=max(1, min(args.subgroup_items, 20)))

    print(render_architecture())
    print()
    print(render_subgroup_contract(contract))
    print()
    print(render_decision_groups(groups))
    print()
    total_subgroups = sum(len(build_subgroups(group, cleanup.items)) for group in groups)
    print(f"PROJECT_ROOTS      = {len(project_roots)}")
    print(f"RAW_APPROVAL_ITEMS = {cleanup.approval_items}")
    print(f"SUBGROUP_ITEMS     = {len(contract.items)}")
    print(f"DECISION_GROUPS    = {len(groups)}")
    print(f"SEMANTIC_SUBGROUPS = {total_subgroups}")
    print("APPROVED           = False")
    print("EXECUTED           = False")
    print("RESULT             = SUBGROUP_CONTRACT_PREVIEW")
    print("MESSAGE            = Review the 10-20 low-risk exact items before any group approval is enabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
