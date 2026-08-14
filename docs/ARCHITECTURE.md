# AI Lab OS Architecture

## Design rule

AI Lab OS is a composition layer over proven execution capabilities. `AI-Lab-Brain` remains the current execution/reliability core; this project organizes higher-level supervision, routing, skills, learning and observability around it.

## Layers

### 1. Supervisor / Goal Manager
- Natural-language goal understanding
- Task decomposition
- Success criteria
- Completion decision

### 2. Agent Runtime
- Task state
- Tool/agent routing
- Context management
- Scheduler/queue
- Pause/resume/checkpoint

### 3. Agents
- Coding Agent
- Research Agent
- Computer Agent

### 4. Skill System
Reusable domain abilities loaded by the runtime rather than hard-coded into the brain. Planned examples: ComfyUI, IELTS, Dahua, Video, Browser, Office, Data, Blender.

### 5. Reliability Core
- Safety
- Approval
- Allowed scope / file guard
- Verification
- Retry
- Repair
- Replan
- Rollback
- Checkpoint

### 6. Change Control
Tests passing does not automatically authorize publication. Candidate changes must pass the relevant diff review, regression tests, security checks, benchmarks and approval gates before commit/deploy/model replacement.

### 7. Intelligence
- Memory
- Model router
- Resource manager

### 8. Learning & Self-Optimization
Measured task outcomes feed reusable skills, prompt/workflow templates, routing policies and optimization candidates. Permanent upgrades require benchmarks and regression checks.

### 9. Observability
- Logging
- Trace
- Metrics
- Audit
- Cost
- GPU/resource use
- Quality score
- Success rate
- Retry/repair counts

## V0.1 scope

V0.1 deliberately starts small: task/plan models, task state, provider routing, reliability policy and event logging. The first milestone is not a large feature surface; it is a clean runtime contract that later connects to the already-proven Brain/Cline/Windows execution loops.
