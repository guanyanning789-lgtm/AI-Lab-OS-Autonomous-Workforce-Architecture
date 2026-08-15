from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_lab_os.capability_gap import CapabilityGapResult, CapabilityMode


class WorkflowDecisionMode(str, Enum):
    DIRECT = "direct"
    COMPOSE = "compose"
    BUILD = "build"


@dataclass(frozen=True)
class WorkflowDecision:
    mode: WorkflowDecisionMode
    reason: str
    primitives: tuple[str, ...] = ()


_DEFAULT_PRIMITIVES = (
    "research",
    "coding",
    "computer",
    "browser",
    "file",
    "knowledge",
)


def decide_dynamic_workflow(
    capability: CapabilityGapResult,
    *,
    available_primitives: tuple[str, ...] = _DEFAULT_PRIMITIVES,
) -> WorkflowDecision:
    if capability.mode is CapabilityMode.DIRECT:
        return WorkflowDecision(
            mode=WorkflowDecisionMode.DIRECT,
            reason="registered skill already matches with sufficient confidence",
        )

    normalized = capability.request.casefold()
    usable: list[str] = []

    keyword_map = {
        "research": ("research", "find", "search", "look up", "资料", "研究", "查找", "搜索"),
        "coding": ("code", "build", "implement", "fix", "program", "开发", "实现", "代码", "修复"),
        "computer": ("click", "open", "window", "desktop", "电脑", "点击", "打开", "窗口"),
        "browser": ("website", "browser", "web", "网页", "浏览器", "网站"),
        "file": ("file", "folder", "disk", "document", "文件", "文件夹", "磁盘", "文档"),
        "knowledge": ("summarize", "organize", "knowledge", "总结", "整理", "知识"),
    }

    allowed = set(available_primitives)
    for primitive, keywords in keyword_map.items():
        if primitive in allowed and any(keyword in normalized for keyword in keywords):
            usable.append(primitive)

    if usable:
        return WorkflowDecision(
            mode=WorkflowDecisionMode.COMPOSE,
            reason="no direct skill matched, but existing primitives appear composable",
            primitives=tuple(usable),
        )

    return WorkflowDecision(
        mode=WorkflowDecisionMode.BUILD,
        reason="no direct skill matched and no existing primitive composition is evident",
    )
