from __future__ import annotations

from dataclasses import dataclass

from ai_lab_os.goal_query_service import GoalStatusSnapshot
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.unified_goal_service import GoalSubmissionRequest, GoalSubmissionResult


@dataclass(frozen=True)
class FinalGoalResult:
    goal_id: str
    status: str
    progress_percent: int
    message: str
    skill_id: str
    handed_off: bool
    resume_cursor: str | None


class FinalNaturalLanguageEntrypoint:
    """V1.0 user-facing boundary: one sentence in, final shaped result out.

    Internal Goal/Skill/TaskPlan/Supervisor/Recovery objects stay behind this
    boundary. Transport (CLI/HTTP/voice/UI) can call the same method later.
    """

    def __init__(self, runtime: ProductRuntime) -> None:
        self.runtime = runtime

    def run(self, request: str, *, goal_id: str | None = None) -> FinalGoalResult:
        text = request.strip()
        if not text:
            raise ValueError("request must not be empty")
        submitted = self.runtime.submit(GoalSubmissionRequest(goal=text, goal_id=goal_id))
        snapshot = self.runtime.get_goal(submitted.goal_id)
        return self._shape(submitted, snapshot)

    @staticmethod
    def _shape(submitted: GoalSubmissionResult, snapshot: GoalStatusSnapshot) -> FinalGoalResult:
        return FinalGoalResult(
            goal_id=submitted.goal_id,
            status=snapshot.status,
            progress_percent=snapshot.progress_percent,
            message=submitted.message,
            skill_id=submitted.skill_id,
            handed_off=submitted.handed_off,
            resume_cursor=snapshot.resume_cursor,
        )
