# AI Lab OS — Autonomous Workforce Architecture

> 越使用越快：Autonomous Execution → Autonomous Learning → Safe Self-Optimization.

AI Lab OS is the long-term orchestration layer for a personal AI workforce. The repository starts from the architecture we defined together: one user entrypoint, a Supervisor, an Agent Runtime, reusable Agents and Skills, a Reliability Core, Change Control, Intelligence, Learning/Self-Optimization, and Observability.

## North-star outcome

A user should be able to state one natural-language goal, for example:

- “修复 AI Lab 的 Cline 调用失败，并测试通过后提交候选变更。”
- “批量设计一组高质量 ComfyUI 电影镜头，不合格就自动重做。”
- “根据我的长期表现安排今天 IELTS 训练，并自动复习错题。”
- “修复大华设备上的 YouTube 全屏问题并在真机上验证。”

AI Lab OS should then understand the goal, plan, route work to the right agents/skills, execute, verify, recover from failure, preserve safety boundaries, learn from the run, and report a structured result.

## Target architecture

1. **Supervisor / Goal Manager** — understand goals, create plans, define success criteria.
2. **Agent Runtime** — task state, routing, context, scheduling, pause/resume.
3. **Agents** — Coding, Research, Computer.
4. **Skill System** — ComfyUI, IELTS, Dahua, Video, Browser, Office, etc.
5. **Reliability Core** — safety, approval, scope guards, verification, retry, repair, replan, rollback.
6. **Change Control** — diff review, regression, benchmark, approval, commit/deploy gates.
7. **Intelligence** — memory, model routing, resource management.
8. **Learning & Self-Optimization** — learn winning workflows, prompts, parameters and routing policies from measured outcomes.
9. **Observability** — logs, traces, metrics, audit, cost, GPU use, quality score, success rate.

## Relationship to AI-Lab-Brain

`AI-Lab-Brain` remains the proven execution/reliability core. This repository is the higher-level OS architecture that will progressively compose and govern those capabilities rather than rewrite them from scratch.

## Development principle

We build vertical closed loops first, then expand horizontally. Every new layer must preserve the ability to execute a real task end-to-end and verify it.
