from __future__ import annotations

import re
from dataclasses import dataclass

from ai_lab_os.skill_compiler import CompiledSkillPlan, compile_skill_plan
from ai_lab_os.skill_contract import SkillContract
from ai_lab_os.skill_registry import SkillRegistry


_TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)


@dataclass(frozen=True)
class SkillSelection:
    skill: SkillContract
    score: int
    matched_terms: tuple[str, ...]
    explicit_trigger_matches: int = 0
    first_trigger_position: int | None = None


@dataclass(frozen=True)
class RoutedSkillRequest:
    request: str
    selection: SkillSelection
    extracted_inputs: dict[str, str]
    compiled: CompiledSkillPlan


def _normalize(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(text) if len(token) >= 2}


def _triggers(skill: SkillContract) -> tuple[str, ...]:
    raw = skill.metadata.get("triggers", "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _score_skill(request: str, skill: SkillContract) -> SkillSelection:
    normalized = _normalize(request)
    request_tokens = _tokens(request)
    score = 0
    matches: list[str] = []
    explicit_trigger_matches = 0
    trigger_positions: list[int] = []

    identity_phrases = ((skill.skill_id, 8), (skill.name, 10))
    for phrase, weight in identity_phrases:
        clean = _normalize(phrase)
        if clean and clean in normalized:
            score += weight
            matches.append(phrase)

    for trigger in _triggers(skill):
        clean = _normalize(trigger)
        if clean:
            position = normalized.find(clean)
            if position >= 0:
                score += 12
                explicit_trigger_matches += 1
                trigger_positions.append(position)
                matches.append(trigger)

    description_overlap = request_tokens & _tokens(skill.description)
    input_overlap = request_tokens & {
        token
        for spec in skill.inputs
        for token in (_tokens(spec.name) | _tokens(spec.description))
    }
    score += len(description_overlap) * 2
    score += len(input_overlap)
    matches.extend(sorted(description_overlap | input_overlap))

    return SkillSelection(
        skill=skill,
        score=score,
        matched_terms=tuple(dict.fromkeys(matches)),
        explicit_trigger_matches=explicit_trigger_matches,
        first_trigger_position=min(trigger_positions) if trigger_positions else None,
    )


def _position_rank(selection: SkillSelection) -> int:
    return selection.first_trigger_position if selection.first_trigger_position is not None else 10**9


def select_skill(request: str, registry: SkillRegistry, *, min_score: int = 2) -> SkillSelection:
    clean_request = request.strip()
    if not clean_request:
        raise ValueError("skill request cannot be empty")
    candidates = sorted(
        (_score_skill(clean_request, skill) for skill in registry.list()),
        key=lambda item: (
            -item.explicit_trigger_matches,
            -item.score,
            _position_rank(item),
            item.skill.skill_id,
        ),
    )
    if not candidates or candidates[0].score < min_score:
        raise LookupError("no registered skill matched the request with sufficient confidence")
    if len(candidates) > 1:
        top = candidates[0]
        second = candidates[1]
        if (
            top.explicit_trigger_matches == second.explicit_trigger_matches
            and top.score == second.score
            and _position_rank(top) == _position_rank(second)
        ):
            raise LookupError(
                "ambiguous skill request: "
                f"{top.skill.skill_id}, {second.skill.skill_id}"
            )
    return candidates[0]


def extract_skill_inputs(request: str, skill: SkillContract) -> dict[str, str]:
    """Extract conservative inputs without inventing values.

    Explicit `name=value` or `name: value` pairs are accepted. If exactly one
    required input remains unresolved, the whole natural-language request is
    used as that input; multiple unresolved required inputs fail closed.
    """

    extracted: dict[str, str] = {}
    for spec in skill.inputs:
        name = re.escape(spec.name)
        match = re.search(
            rf"(?:^|\s){name}\s*(?:=|:)\s*(.+?)(?=\s+[\w\-]+\s*(?:=|:)|$)",
            request,
            flags=re.IGNORECASE,
        )
        if match:
            value = match.group(1).strip().strip('"\'')
            if value:
                extracted[spec.name] = value

    unresolved = [
        spec for spec in skill.inputs
        if spec.required and spec.name not in extracted and spec.default is None
    ]
    if len(unresolved) == 1:
        extracted[unresolved[0].name] = request.strip()
    elif len(unresolved) > 1:
        names = ", ".join(spec.name for spec in unresolved)
        raise ValueError(f"cannot safely infer multiple required skill inputs: {names}")
    return extracted


def route_skill_request(
    request: str,
    registry: SkillRegistry,
    *,
    goal_id: str,
    min_score: int = 2,
) -> RoutedSkillRequest:
    selection = select_skill(request, registry, min_score=min_score)
    inputs = extract_skill_inputs(request, selection.skill)
    compiled = compile_skill_plan(selection.skill, inputs, goal_id=goal_id)
    return RoutedSkillRequest(
        request=request.strip(),
        selection=selection,
        extracted_inputs=inputs,
        compiled=compiled,
    )
