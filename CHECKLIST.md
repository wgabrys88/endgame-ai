# CHECKLIST — grok-dev test session

Run from repo root on branch `grok-dev`.

## Before start

- [ ] LM Studio running with nemotron-3-nano loaded (or use `--backend acp`)
- [ ] `git checkout grok-dev && git pull`
- [ ] No stale processes: close prior `tui.py` / `reactor.py` runs
- [ ] `runtime/comms/` will be wiped on TUI start (sessions preserved)

## Launch

```bash
python tui.py --model-profile nemotron
```

- [ ] TUI renders 45 lines, no flicker/tearing
- [ ] Header shows session id, `5/5 slots` (not 10/5)
- [ ] Slots appear within 2s (not empty for minutes)

## Stability (false respawn fix)

- [ ] Slots stay alive > 30s while `planner.pending` (no restart every 5s)
- [ ] Session JSONL: **one** `start` per slot, not 10+ restarts
- [ ] No `stop` events unless you quit

## Orchestrator

- [ ] Only comms_operator shows active LLM initially
- [ ] Workers (s2-s5) idle — last phase stays empty or low activity
- [ ] After ~20s: comms emits `moe.route` in s1 events
- [ ] Target worker receives `route` in inbox → wakes → `planner.pending`

## Blackboard v1

```bash
python comms.py state
```

- [ ] Shows structured telemetry per persona (`pwr`, `stag`, `vel`, `slot`)
- [ ] `messages.json` entries have `"v": 1` and `"payload": {...}`
- [ ] `events_bus.jsonl` has `kind=telemetry` lines (not prose beacons)

## MoE escalation (optional — simulate stuck worker)

Post high stagnation manually or wait for natural stuck state:

- [ ] When `stag >= 0.7` and `vel ≈ 0` for 5 telemetry cycles (~150s with 30s beacon)
- [ ] s1 logs `moe.escalate`
- [ ] `control.jsonl` drained by reactor → `MOE REASSIGN sN -> quality_critic` in reactor stdout
- [ ] `messages.json` has `kind=route` with `"escalate": true`

## Human interrupt

In TUI type: `@implementor read config.py and summarize`

- [ ] Message appears in BUS CHAT
- [ ] implementor wakes (planner.pending on s3)
- [ ] Human message has `pri=3`

## TUI bus panel

- [ ] CHAT shows recent messages with `[route]` / `[ping]` kind tags
- [ ] EVENTS shows pipeline events
- [ ] s1 active agent shows `moe` after routing cycle

## ACP (if testing)

```bash
python tui.py --backend acp
```

- [ ] No `ACP_WORKSPACE_BASE` import errors
- [ ] Sequential LLM lock prevents parallel timeouts

## Git sanity

```bash
git status
git log --oneline -5
```

- [ ] On `grok-dev`, latest commit includes MoE + bus v1 + docs

## Pass criteria

**Minimum viable:** slots stable, orchestrator idle workers, one `moe.route` per 20s, bus v1 telemetry structured.

**Full glory:** escalation reassigns stuck slot, human @mention wakes worker, TUI clean.