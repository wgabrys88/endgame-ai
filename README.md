# endgame-ai

Endgame-AI is a Windows runtime for event-driven LLM work. The current architecture is contract-bus first: every task, contract, action, evidence item, claim, verdict, capability, and runtime event uses one JSON record envelope.

## Runtime Contract

Every bus record is shaped as:

```json
{
  "schema_version": "contract-bus.v1",
  "record_id": "string",
  "record_type": "task|contract|action|evidence|claim|verdict|capability|runtime_event",
  "created_at": "ISO-8601",
  "cycle_id": "string",
  "root_task_id": "string",
  "parent_task_id": "string|null",
  "task_id": "string|null",
  "role": "planner|actor|observer|verifier|reviewer|runtime|tool",
  "agent_id": "string|null",
  "data": {}
}
```

The root user goal is mission context. The planner creates subtasks and contracts. The runtime activates one task, the actor mutates state and publishes actions/claims/tool evidence, the observer publishes read-only evidence, and the verifier judges the active task against its active contract from bus records only.

## Verification Rules

The verifier always receives one `verification-packet.v1` object:

```json
{
  "schema_version": "verification-packet.v1",
  "root_task": {},
  "active_task": {},
  "active_contract": {},
  "records": {
    "actions": [],
    "evidence": [],
    "claims": [],
    "prior_verdicts": [],
    "runtime_events": []
  },
  "verifier_capability": {}
}
```

Actor claims are never primary proof. Successful action execution is not completion proof. Keyword matching and app-specific verifier logic are not valid verification. Missing required evidence returns `UNKNOWN`; contradictory evidence returns `NOT_DONE`; all required success conditions satisfied by accepted evidence returns `DONE`.

## Status Model

Tasks move through one runtime transition model:

- `proposed -> active`
- `active -> claimed_done`
- `claimed_done -> verified_done`
- `active -> verified_done`
- `active -> blocked`
- `active -> rejected`
- `active -> active` when the verifier returns `UNKNOWN`

Only verifier `DONE` can mark a task `verified_done`.

## RBAC

Capabilities are enforced before runtime operations:

- Actor can mutate UI, artifacts, and execute commands.
- Verifier can observe, read, verify, and publish verdicts; it cannot mutate.
- Reviewer can observe, read, publish review notes/claims/verdicts; it cannot mutate.
- Forbidden mutation attempts are blocked and logged as `permission_denied` runtime events.

## Main Entry Points

```powershell
python main.py "goal" --backend lmstudio
python tui.py "goal" --mode unicore --model-profile nemotron
python reactor.py --mode colony --model-profile nemotron_parallel --goal "goal"
```

## Core Files

- `agents.py` - planner, actor, observer, verifier, status transitions, RBAC, contract-bus record normalization.
- `comms.py` - blackboard storage and compatibility projection for existing readers.
- `engine.py` - runtime loop and pipeline dispatch.
- `actions.py` - UI, file, and command action execution.
- `desktop.py` - Windows UI Automation observer.
- `prompts/` - role prompts aligned to the contract-bus verifier path.
- `tui.py` - contract-bus runtime display.

## Development Notes

Do not add a fallback verifier, task-specific verifier branch, keyword-only proof path, or app-specific verification field. Add new behavior by publishing normalized bus records and extending contracts, not by bypassing the verifier packet.
