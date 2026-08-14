from ai_lab_os.storage_cleanup_plan import CleanupAction, CleanupItem, CleanupPlan
from ai_lab_os.storage_decision_groups import DecisionGroup, DecisionGroupKind
from ai_lab_os.storage_group_detail import build_group_detail, render_group_details


def test_group_detail_summarizes_actions_size_targets_and_risk() -> None:
    plan = CleanupPlan(
        items=(
            CleanupItem("C:/Downloads/a.pdf", CleanupAction.MIGRATE, 100, True, "move", "D:/Knowledge/Documents/a.pdf"),
            CleanupItem("C:/Downloads/b.pdf", CleanupAction.MIGRATE, 200, True, "move", "D:/Knowledge/Documents/b.pdf"),
        ),
        estimated_reclaimable_bytes=0,
        duplicate_groups=0,
        approval_items=2,
        blocked_items=0,
        truncated_scan=False,
    )
    group = DecisionGroup("downloads", DecisionGroupKind.DOWNLOADS_BATCH, 2, True, "docs", ("C:/Downloads/a.pdf", "C:/Downloads/b.pdf"))
    detail = build_group_detail(group, plan)
    assert detail.item_count == 2
    assert detail.total_bytes == 300
    assert detail.actions == (("migrate", 2),)
    assert detail.rollback_capable is True
    assert "MEDIUM" in detail.risk
    assert "D:" in detail.destinations[0]


def test_review_group_is_not_claimed_rollback_ready() -> None:
    plan = CleanupPlan(
        items=(CleanupItem("C:/Desktop/model.gguf", CleanupAction.REVIEW, 10, True, "review"),),
        estimated_reclaimable_bytes=0,
        duplicate_groups=0,
        approval_items=1,
        blocked_items=0,
        truncated_scan=False,
    )
    group = DecisionGroup("other", DecisionGroupKind.OTHER, 1, True, "review", ("C:/Desktop/model.gguf",))
    detail = build_group_detail(group, plan)
    assert detail.rollback_capable is False
    assert "HIGH" in detail.risk


def test_renderer_expands_only_limited_examples() -> None:
    plan = CleanupPlan(
        items=tuple(CleanupItem(f"C:/Desktop/{i}.png", CleanupAction.MIGRATE, 1, True, "move", f"D:/AI-Lab/Media/Images/{i}.png") for i in range(4)),
        estimated_reclaimable_bytes=0,
        duplicate_groups=0,
        approval_items=4,
        blocked_items=0,
        truncated_scan=False,
    )
    group = DecisionGroup("desktop", DecisionGroupKind.DESKTOP_BATCH, 4, True, "images", tuple(item.path for item in plan.items))
    text = render_group_details((group,), plan, max_examples=2)
    assert "... 2 more items" in text
    assert "risk" in text
