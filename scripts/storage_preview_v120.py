from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_lab_os.storage_approval_contract import build_approval_contract, render_approval_contract
from ai_lab_os.storage_canonical_architecture import render_architecture
from ai_lab_os.storage_cleanup_plan import build_cleanup_plan
from ai_lab_os.storage_collision_guard import guard_plan
from ai_lab_os.storage_curator import StoragePlan, build_storage_plan
from ai_lab_os.storage_decision_groups import build_decision_groups, render_decision_groups
from ai_lab_os.storage_intelligence import apply_project_boundaries, build_version_families
from ai_lab_os.storage_migration_blueprint import build_migration_blueprint, render_migration_blueprint
from ai_lab_os.storage_path_planner import build_migration_plan
from ai_lab_os.storage_project_roots import apply_project_root_protection, detect_project_roots
from ai_lab_os.storage_subgroups import build_subgroups


def existing_user_roots() -> tuple[Path, ...]:
    home = Path.home()
    candidates = (home / "Downloads", home / "Desktop", Path(r"C:\AI-Lab"), Path(r"D:\AI-Lab"))
    return tuple(path for path in candidates if path.exists())


def main() -> int:
    parser = argparse.ArgumentParser(description="Storage Curator V1.3.1 exact approval contract preview")
    parser.add_argument("--max-files", type=int, default=100000)
    parser.add_argument("--duplicate-min-mb", type=int, default=100)
    parser.add_argument("--blueprint-items", type=int, default=10)
    parser.add_argument("--contract-items", type=int, default=3)
    args = parser.parse_args()

    roots = existing_user_roots()
    print("=" * 78)
    print("STORAGE CURATOR V1.3.1 EXACT APPROVAL CONTRACT PREVIEW")
    print("=" * 78)
    print("MODE   = READ ONLY / CONTRACT PREVIEW")
    print("SAFETY = PDF/image candidates only; exact path + destination + SHA256 bound; no execution")
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
    contract = build_approval_contract(blueprint, limit=max(1, min(args.contract_items, 3)))

    print(render_architecture())
    print()
    print(render_migration_blueprint(blueprint, max_items=max(1, args.blueprint_items)))
    print()
    print(render_approval_contract(contract))
    print()
    print(render_decision_groups(groups))
    print()
    total_subgroups = sum(len(build_subgroups(group, cleanup.items)) for group in groups)
    print(f"PROJECT_ROOTS             = {len(project_roots)}")
    print(f"RAW_APPROVAL_ITEMS        = {cleanup.approval_items}")
    print(f"MIGRATION_BLUEPRINT_ITEMS = {len(blueprint)}")
    print(f"CONTRACT_ITEMS            = {len(contract.items)}")
    print(f"DECISION_GROUPS           = {len(groups)}")
    print(f"SEMANTIC_SUBGROUPS        = {total_subgroups}")
    print("APPROVED                  = False")
    print("EXECUTED                  = False")
    print("RESULT                    = CONTRACT_PREVIEW")
    print("MESSAGE                   = Exact source/destination/hash contract generated. Real execution remains disabled until explicit approval of these exact items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
