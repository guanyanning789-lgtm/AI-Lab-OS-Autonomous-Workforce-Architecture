from ai_lab_os.storage_cleanup_plan import CleanupAction, build_cleanup_plan, render_cleanup_plan
from ai_lab_os.storage_curator import DuplicateGroup, FileCandidate, StorageDisposition, StoragePlan


def test_cleanup_plan_never_marks_actions_as_preapproved() -> None:
    storage = StoragePlan(
        candidates=(
            FileCandidate("duplicate.bin", 100, 10, StorageDisposition.DUPLICATE, "duplicate"),
            FileCandidate("old.tmp", 200, 60, StorageDisposition.CLEAN_CANDIDATE, "old temp"),
            FileCandidate("model.gguf", 300, 100, StorageDisposition.REVIEW, "model"),
            FileCandidate("pagefile.sys", 400, 1, StorageDisposition.PROTECTED, "protected"),
        ),
        duplicates=(DuplicateGroup("abc", 100, ("keep.bin", "duplicate.bin"), 100),),
        reclaimable_bytes=300,
        scanned_files=4,
        truncated=False,
    )
    plan = build_cleanup_plan(storage)
    by_path = {item.path: item for item in plan.items}
    assert by_path["duplicate.bin"].action is CleanupAction.DELETE_DUPLICATE
    assert by_path["duplicate.bin"].approval_required is True
    assert by_path["old.tmp"].action is CleanupAction.CLEAN
    assert by_path["old.tmp"].approval_required is True
    assert by_path["model.gguf"].action is CleanupAction.REVIEW
    assert by_path["model.gguf"].approval_required is True
    assert by_path["pagefile.sys"].action is CleanupAction.BLOCK
    assert by_path["pagefile.sys"].approval_required is False
    assert plan.estimated_reclaimable_bytes == 300


def test_renderer_explicitly_says_no_changes_executed() -> None:
    plan = StoragePlan(candidates=(), duplicates=(), reclaimable_bytes=0, scanned_files=0, truncated=True)
    text = render_cleanup_plan(build_cleanup_plan(plan))
    assert "NO CHANGES EXECUTED" in text
    assert "SCAN                  = PARTIAL" in text
