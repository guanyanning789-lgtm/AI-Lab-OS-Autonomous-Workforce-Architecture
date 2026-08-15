from ai_lab_os.capability_gap import CapabilityGapReason, CapabilityGapResult, CapabilityMode
from ai_lab_os.dynamic_workflow_decision import WorkflowDecisionMode, decide_dynamic_workflow


def direct(request: str = "check disk") -> CapabilityGapResult:
    return CapabilityGapResult(request=request, mode=CapabilityMode.DIRECT, reason=None, selected_skill_id="disk", selected_score=10, matched_terms=("disk",))


def gap(request: str) -> CapabilityGapResult:
    return CapabilityGapResult(request=request, mode=CapabilityMode.GAP, reason=CapabilityGapReason.NO_MATCH, selected_skill_id=None, selected_score=None, matched_terms=())


def test_direct_skill_stays_direct() -> None:
    result = decide_dynamic_workflow(direct())
    assert result.mode is WorkflowDecisionMode.DIRECT


def test_unknown_research_and_code_goal_composes_existing_primitives() -> None:
    result = decide_dynamic_workflow(gap("研究这个新格式，然后写代码实现转换器"))
    assert result.mode is WorkflowDecisionMode.COMPOSE
    assert result.primitives == ("research", "coding")


def test_file_browser_goal_composes_without_new_skill() -> None:
    result = decide_dynamic_workflow(gap("打开网站并整理下载的文件"))
    assert result.mode is WorkflowDecisionMode.COMPOSE
    assert "browser" in result.primitives
    assert "file" in result.primitives


def test_novel_goal_with_no_evident_primitive_requires_build() -> None:
    result = decide_dynamic_workflow(gap("建立自适应雅思教练系统"))
    assert result.mode is WorkflowDecisionMode.BUILD


def test_available_primitive_filter_is_respected() -> None:
    result = decide_dynamic_workflow(gap("research and code this"), available_primitives=("research",))
    assert result.mode is WorkflowDecisionMode.COMPOSE
    assert result.primitives == ("research",)
