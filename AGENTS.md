# Session Checklist — Event Budget (2026-06-09)

## CONCEPT

The blackboard event stream is the single source of truth.
Every runtime event flows through `persistence.append_runtime_event()`.
The EVENT BUDGET is the execution boundary: system stops after N events.

## IMPLEMENTATION STATUS

- [x] `config.EVENT_BUDGET` (default 100, mutable via CLI)
- [x] `--event-budget N` CLI argument in main.py
- [x] Counter in `persistence.append_runtime_event()`
- [x] `budget_exhausted()` flag checked in orchestrator loop
- [x] Graceful exit path with log event + TUI render
- [x] `event_count()` exported for metrics
- [x] `run.end` log includes events_used and event_budget
- [x] `analyze_run.py` reports budget usage percentage
- [x] Proactive verification on last plan step
- [x] Dead code removal: `_instruction_for_actor` identity function
- [x] Pyright: 0 errors, 0 warnings, 0 informations

## USAGE

```
python main.py "open notepad" --backend acp --event-budget 50
python main.py "emit done" --backend lmstudio --event-budget 200
python analyze_run.py blackboard_events.txt
```

## SCIENTIFIC VALUE

Fixed event count per experiment enables:
- Comparing backends (ACP vs LM Studio) under identical resource constraints
- Measuring efficiency: successful_actions / total_events
- Measuring waste: LLM calls that produce no state change
- Reproducible experiments with bounded resource usage
- Evolutionary pressure: system must accomplish MORE in FEWER events

## ASCII ARCHITECTURE

```
CLI --event-budget=100
        │
        ▼
config.EVENT_BUDGET = 100
        │
        ▼
┌──────────────────────────────┐
│  persistence.append_runtime_ │
│  event(record)               │
│    _event_counter++          │◄── EVERY event passes here
│    if >= budget:             │
│      _budget_exhausted=True  │
└──────────────────────────────┘
        │
        ▼
orchestrator._loop():
  while True:
    if budget_exhausted():     ◄── checked BEFORE each iteration
      log + graceful exit
      return False
    ...normal iteration...
```
