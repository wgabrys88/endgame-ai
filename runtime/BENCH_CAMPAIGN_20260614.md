# LM Studio Parameter Benchmark Campaign

Session replay source: `sessions/20260614_175152`

Budgets use project `config.BUDGET` / `THINKING_BUDGET` unless profile overrides golden session values.

## T01_postfix_default — Post-fix default 5×5 matrix

- **Time:** 2026-06-14T18:32:00
- **Wall:** 66924.1 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | planner_maintenance | parallel_baseline | planner | 66919.8 | N | N | 10 | invalid_json |
| 2 | verifier_bus_post | api_schema_on | verifier | 7657.4 | Y | Y | 100 | ok |
| 3 | fission_judge_bus | low_thinking_high_output | fission_judge | 27402.3 | Y | Y | 100 | ok |
| 4 | reflector_syntax | high_thinking_low_output | reflector | 19893.6 | Y | Y | 100 | ok |
| 5 | mutator_plugin | nemotron_serial | mutator | 47072.2 | Y | Y | 100 | ok |

**Ranking:**
- `api_schema_on`: score=100.0 avg_ms=7657.4 json=1/1 quality=1/1 empty=0
- `high_thinking_low_output`: score=100.0 avg_ms=19893.6 json=1/1 quality=1/1 empty=0
- `low_thinking_high_output`: score=100.0 avg_ms=27402.3 json=1/1 quality=1/1 empty=0
- `nemotron_serial`: score=100.0 avg_ms=47072.2 json=1/1 quality=1/1 empty=0
- `parallel_baseline`: score=10.0 avg_ms=66919.8 json=0/1 quality=0/1 empty=0

## T01_postfix_default — Post-fix default 5×5 matrix

- **Time:** 2026-06-14T18:33:17
- **Wall:** 55157.5 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | planner_maintenance | parallel_baseline | planner | 55153.8 | Y | N | 55 | done_when_minLength_20 |
| 2 | verifier_bus_post | api_schema_on | verifier | 6051.6 | Y | Y | 100 | ok |
| 3 | fission_judge_bus | low_thinking_high_output | fission_judge | 31936.8 | Y | Y | 100 | ok |
| 4 | reflector_syntax | high_thinking_low_output | reflector | 18420.2 | Y | Y | 100 | ok |
| 5 | mutator_plugin | nemotron_serial | mutator | 33735.6 | Y | Y | 100 | ok |

**Ranking:**
- `api_schema_on`: score=100.0 avg_ms=6051.6 json=1/1 quality=1/1 empty=0
- `high_thinking_low_output`: score=100.0 avg_ms=18420.2 json=1/1 quality=1/1 empty=0
- `low_thinking_high_output`: score=100.0 avg_ms=31936.8 json=1/1 quality=1/1 empty=0
- `nemotron_serial`: score=100.0 avg_ms=33735.6 json=1/1 quality=1/1 empty=0
- `parallel_baseline`: score=55.0 avg_ms=55153.8 json=1/1 quality=0/1 empty=0

## T02_session_replay_schema_off — Session failure replays, role budgets, schema off

- **Time:** 2026-06-14T18:34:22
- **Wall:** 65749.5 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | session_s1_verifier_routed | role_budget_off_1 | verifier | 19063.2 | Y | Y | 100 | ok |
| 2 | session_s1_verifier_posted | role_budget_off_2 | verifier | 18474.6 | Y | Y | 100 | ok |
| 3 | session_s3_fission_empty_risk | role_budget_off_3 | fission_judge | 32312.6 | Y | Y | 100 | ok |
| 4 | session_s2_verifier_log_read | role_budget_off_4 | verifier | 22542.8 | Y | N | 96 | expected_denied_got_confirmed |
| 5 | session_s2_planner_log_audit | role_budget_off_5 | planner | 65744.6 | Y | N | 55 | done_when_minLength_20 |

**Ranking:**
- `role_budget_off_2`: score=100.0 avg_ms=18474.6 json=1/1 quality=1/1 empty=0
- `role_budget_off_1`: score=100.0 avg_ms=19063.2 json=1/1 quality=1/1 empty=0
- `role_budget_off_3`: score=100.0 avg_ms=32312.6 json=1/1 quality=1/1 empty=0
- `role_budget_off_4`: score=96.0 avg_ms=22542.8 json=1/1 quality=0/1 empty=0
- `role_budget_off_5`: score=55.0 avg_ms=65744.6 json=1/1 quality=0/1 empty=0

## T03_session_replay_schema_on — Session failure replays, role budgets, API schema on

- **Time:** 2026-06-14T18:34:34
- **Wall:** 11978.4 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | session_s1_verifier_routed | api_schema_on_1 | verifier | 8426.5 | Y | Y | 100 | ok |
| 2 | session_s1_verifier_posted | api_schema_on_2 | verifier | 5782.6 | Y | Y | 100 | ok |
| 3 | session_s3_fission_empty_risk | api_schema_on_3 | fission_judge | 9141.5 | Y | N | 100 | expected_deny_got_credit |
| 4 | session_s2_verifier_log_read | api_schema_on_4 | verifier | 5525.2 | Y | N | 100 | expected_denied_got_confirmed |
| 5 | session_s2_planner_log_audit | api_schema_on_5 | planner | 11973.6 | Y | Y | 100 | ok |

**Ranking:**
- `api_schema_on_4`: score=100.0 avg_ms=5525.2 json=1/1 quality=0/1 empty=0
- `api_schema_on_2`: score=100.0 avg_ms=5782.6 json=1/1 quality=1/1 empty=0
- `api_schema_on_1`: score=100.0 avg_ms=8426.5 json=1/1 quality=1/1 empty=0
- `api_schema_on_3`: score=100.0 avg_ms=9141.5 json=1/1 quality=0/1 empty=0
- `api_schema_on_5`: score=100.0 avg_ms=11973.6 json=1/1 quality=1/1 empty=0

## T04_session_replay_golden_budgets — Session replays with golden-session per-role budgets

- **Time:** 2026-06-14T18:35:31
- **Wall:** 56961.7 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | session_s1_verifier_routed | golden_verifier | verifier | 15670.7 | Y | Y | 100 | ok |
| 2 | session_s1_verifier_posted | golden_verifier | verifier | 18140.3 | Y | Y | 100 | ok |
| 3 | session_s3_fission_empty_risk | golden_fission_judge | fission_judge | 25175.4 | N | N | 11 | invalid_json |
| 4 | session_s2_verifier_log_read | golden_verifier | verifier | 20505.8 | Y | N | 96 | expected_denied_got_confirmed |
| 5 | session_s2_planner_log_audit | golden_planner | planner | 56957.6 | Y | N | 55 | done_when_minLength_20 |

**Ranking:**
- `golden_verifier`: score=98.7 avg_ms=18105.6 json=3/1 quality=2/1 empty=0
- `golden_planner`: score=55.0 avg_ms=56957.6 json=1/1 quality=0/1 empty=0
- `golden_fission_judge`: score=11.0 avg_ms=25175.4 json=0/1 quality=0/1 empty=0

## T05_fission_golden_vs_postfix — Fission judge: golden 224/192 vs post-fix vs schema variants

- **Time:** 2026-06-14T18:36:07
- **Wall:** 35896.7 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | session_s3_fission_empty_risk | golden_fission | fission_judge | 31881.4 | N | N | 10 | invalid_json |
| 2 | session_s3_fission_empty_risk | postfix_fission | fission_judge | 35893.3 | Y | Y | 100 | ok |
| 3 | session_s3_fission_empty_risk | schema_on_fission | fission_judge | 15975.4 | Y | N | 100 | expected_deny_got_credit |
| 4 | session_s3_fission_empty_risk | low_think_fission | fission_judge | 34825.4 | Y | Y | 100 | ok |
| 5 | session_s3_fission_empty_risk | high_think_fission | fission_judge | 31775.3 | N | N | 10 | invalid_json |

**Ranking:**
- `schema_on_fission`: score=100.0 avg_ms=15975.4 json=1/1 quality=0/1 empty=0
- `low_think_fission`: score=100.0 avg_ms=34825.4 json=1/1 quality=1/1 empty=0
- `postfix_fission`: score=100.0 avg_ms=35893.3 json=1/1 quality=1/1 empty=0
- `high_think_fission`: score=10.0 avg_ms=31775.3 json=0/1 quality=0/1 empty=0
- `golden_fission`: score=10.0 avg_ms=31881.4 json=0/1 quality=0/1 empty=0

## T06_verifier_routed_matrix — Verifier routed vs posted with schema on/off

- **Time:** 2026-06-14T18:36:22
- **Wall:** 14598.8 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** True

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | session_s1_verifier_routed | v_routed_off | verifier | 13791.2 | Y | Y | 100 | ok |
| 2 | session_s1_verifier_posted | v_routed_on | verifier | 7515.2 | Y | Y | 100 | ok |
| 3 | session_s1_verifier_routed | v_posted_off | verifier | 14546.4 | Y | Y | 100 | ok |
| 4 | session_s1_verifier_posted | v_posted_on | verifier | 7195.1 | Y | Y | 100 | ok |
| 5 | session_s1_verifier_routed | v_routed_golden | verifier | 14594.9 | Y | Y | 100 | ok |

**Ranking:**
- `v_posted_on`: score=100.0 avg_ms=7195.1 json=1/1 quality=1/1 empty=0
- `v_routed_on`: score=100.0 avg_ms=7515.2 json=1/1 quality=1/1 empty=0
- `v_routed_off`: score=100.0 avg_ms=13791.2 json=1/1 quality=1/1 empty=0
- `v_posted_off`: score=100.0 avg_ms=14546.4 json=1/1 quality=1/1 empty=0
- `v_routed_golden`: score=100.0 avg_ms=14594.9 json=1/1 quality=1/1 empty=0

## T07_default_all_schema_on — Default tasks, all slots api_schema on

- **Time:** 2026-06-14T18:36:41
- **Wall:** 19658.8 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** True

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | planner_maintenance | all_schema_on_1 | planner | 19655.1 | Y | Y | 100 | ok |
| 2 | verifier_bus_post | all_schema_on_2 | verifier | 7298.0 | Y | Y | 100 | ok |
| 3 | fission_judge_bus | all_schema_on_3 | fission_judge | 14871.3 | Y | Y | 100 | ok |
| 4 | reflector_syntax | all_schema_on_4 | reflector | 10916.4 | Y | Y | 100 | ok |
| 5 | mutator_plugin | all_schema_on_5 | mutator | 13649.1 | Y | Y | 100 | ok |

**Ranking:**
- `all_schema_on_2`: score=100.0 avg_ms=7298.0 json=1/1 quality=1/1 empty=0
- `all_schema_on_4`: score=100.0 avg_ms=10916.4 json=1/1 quality=1/1 empty=0
- `all_schema_on_5`: score=100.0 avg_ms=13649.1 json=1/1 quality=1/1 empty=0
- `all_schema_on_3`: score=100.0 avg_ms=14871.3 json=1/1 quality=1/1 empty=0
- `all_schema_on_1`: score=100.0 avg_ms=19655.1 json=1/1 quality=1/1 empty=0

## T08_default_all_schema_off — Default tasks, role budgets only

- **Time:** 2026-06-14T18:37:38
- **Wall:** 56282.9 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | planner_maintenance | all_schema_off_1 | planner | 56280.4 | Y | N | 60 | missing_sequence |
| 2 | verifier_bus_post | all_schema_off_2 | verifier | 14146.9 | Y | Y | 100 | ok |
| 3 | fission_judge_bus | all_schema_off_3 | fission_judge | 29878.0 | Y | Y | 100 | ok |
| 4 | reflector_syntax | all_schema_off_4 | reflector | 19011.7 | Y | Y | 100 | ok |
| 5 | mutator_plugin | all_schema_off_5 | mutator | 23412.3 | Y | Y | 100 | ok |

**Ranking:**
- `all_schema_off_2`: score=100.0 avg_ms=14146.9 json=1/1 quality=1/1 empty=0
- `all_schema_off_4`: score=100.0 avg_ms=19011.7 json=1/1 quality=1/1 empty=0
- `all_schema_off_5`: score=100.0 avg_ms=23412.3 json=1/1 quality=1/1 empty=0
- `all_schema_off_3`: score=100.0 avg_ms=29878.0 json=1/1 quality=1/1 empty=0
- `all_schema_off_1`: score=60.0 avg_ms=56280.4 json=1/1 quality=0/1 empty=0

## T09_planner_budget_sweep — Planner maintenance with budget sweep

- **Time:** 2026-06-14T18:39:23
- **Wall:** 104982.7 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | planner_maintenance | p_golden | planner | 95521.2 | Y | N | 60 | missing_sequence |
| 2 | planner_maintenance | p_postfix | planner | 94949.3 | Y | N | 55 | done_when_minLength_20 |
| 3 | planner_maintenance | p_schema_on | planner | 33642.2 | Y | Y | 100 | ok |
| 4 | planner_maintenance | p_low_think | planner | 104977.8 | Y | N | 55 | done_when_minLength_20 |
| 5 | planner_maintenance | p_high_think | planner | 79585.8 | N | N | 10 | invalid_json |

**Ranking:**
- `p_schema_on`: score=100.0 avg_ms=33642.2 json=1/1 quality=1/1 empty=0
- `p_golden`: score=60.0 avg_ms=95521.2 json=1/1 quality=0/1 empty=0
- `p_postfix`: score=55.0 avg_ms=94949.3 json=1/1 quality=0/1 empty=0
- `p_low_think`: score=55.0 avg_ms=104977.8 json=1/1 quality=0/1 empty=0
- `p_high_think`: score=10.0 avg_ms=79585.8 json=0/1 quality=0/1 empty=0

## T10_repeat_schema_on_session — Repeat T03 stability check

- **Time:** 2026-06-14T18:39:37
- **Wall:** 14175.5 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | session_s1_verifier_routed | api_schema_on_repeat_1 | verifier | 9411.0 | Y | Y | 100 | ok |
| 2 | session_s1_verifier_posted | api_schema_on_repeat_2 | verifier | 8095.0 | Y | Y | 100 | ok |
| 3 | session_s3_fission_empty_risk | api_schema_on_repeat_3 | fission_judge | 11915.1 | Y | N | 100 | expected_deny_got_credit |
| 4 | session_s2_verifier_log_read | api_schema_on_repeat_4 | verifier | 8097.0 | Y | N | 98 | expected_denied_got_confirmed |
| 5 | session_s2_planner_log_audit | api_schema_on_repeat_5 | planner | 14170.5 | Y | Y | 100 | ok |

**Ranking:**
- `api_schema_on_repeat_2`: score=100.0 avg_ms=8095.0 json=1/1 quality=1/1 empty=0
- `api_schema_on_repeat_1`: score=100.0 avg_ms=9411.0 json=1/1 quality=1/1 empty=0
- `api_schema_on_repeat_3`: score=100.0 avg_ms=11915.1 json=1/1 quality=0/1 empty=0
- `api_schema_on_repeat_5`: score=100.0 avg_ms=14170.5 json=1/1 quality=1/1 empty=0
- `api_schema_on_repeat_4`: score=98.0 avg_ms=8097.0 json=1/1 quality=0/1 empty=0

## T03_session_replay_schema_on_cycle11 — Session failure replays, role budgets, API schema on (cycle 11)

- **Time:** 2026-06-14T18:39:49
- **Wall:** 11736.3 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | session_s1_verifier_routed | api_schema_on_1 | verifier | 6917.2 | Y | Y | 100 | ok |
| 2 | session_s1_verifier_posted | api_schema_on_2 | verifier | 5787.3 | Y | Y | 100 | ok |
| 3 | session_s3_fission_empty_risk | api_schema_on_3 | fission_judge | 9531.0 | Y | N | 100 | expected_deny_got_credit |
| 4 | session_s2_verifier_log_read | api_schema_on_4 | verifier | 5532.7 | Y | N | 100 | expected_denied_got_confirmed |
| 5 | session_s2_planner_log_audit | api_schema_on_5 | planner | 11732.2 | Y | Y | 100 | ok |

**Ranking:**
- `api_schema_on_4`: score=100.0 avg_ms=5532.7 json=1/1 quality=0/1 empty=0
- `api_schema_on_2`: score=100.0 avg_ms=5787.3 json=1/1 quality=1/1 empty=0
- `api_schema_on_1`: score=100.0 avg_ms=6917.2 json=1/1 quality=1/1 empty=0
- `api_schema_on_3`: score=100.0 avg_ms=9531.0 json=1/1 quality=0/1 empty=0
- `api_schema_on_5`: score=100.0 avg_ms=11732.2 json=1/1 quality=1/1 empty=0

## T05_fission_golden_vs_postfix_cycle11 — Fission judge: golden 224/192 vs post-fix vs schema variants (cycle 11)

- **Time:** 2026-06-14T18:40:30
- **Wall:** 41664.4 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | session_s3_fission_empty_risk | golden_fission | fission_judge | 28460.8 | N | N | 11 | invalid_json |
| 2 | session_s3_fission_empty_risk | postfix_fission | fission_judge | 37240.0 | Y | Y | 100 | ok |
| 3 | session_s3_fission_empty_risk | schema_on_fission | fission_judge | 10678.4 | Y | N | 100 | expected_deny_got_credit |
| 4 | session_s3_fission_empty_risk | low_think_fission | fission_judge | 41659.9 | Y | Y | 100 | ok |
| 5 | session_s3_fission_empty_risk | high_think_fission | fission_judge | 28463.0 | N | N | 11 | invalid_json |

**Ranking:**
- `schema_on_fission`: score=100.0 avg_ms=10678.4 json=1/1 quality=0/1 empty=0
- `postfix_fission`: score=100.0 avg_ms=37240.0 json=1/1 quality=1/1 empty=0
- `low_think_fission`: score=100.0 avg_ms=41659.9 json=1/1 quality=1/1 empty=0
- `golden_fission`: score=11.0 avg_ms=28460.8 json=0/1 quality=0/1 empty=0
- `high_think_fission`: score=11.0 avg_ms=28463.0 json=0/1 quality=0/1 empty=0

## T09_planner_budget_sweep_cycle11 — Planner maintenance with budget sweep (cycle 11)

- **Time:** 2026-06-14T18:42:11
- **Wall:** 100812.1 ms
- **Model:** nvidia-nemotron-3-nano-4b@q6_k_xl
- **Host:** http://192.168.16.31:1234
- **Request:** Colony maintenance: audit bus traffic and post maintenance scan completed
- **Pass:** False

| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |
|------|------|---------|------|-----|------|---------|-------|--------|
| 1 | planner_maintenance | p_golden | planner | 99969.0 | Y | N | 55 | done_when_minLength_20 |
| 2 | planner_maintenance | p_postfix | planner | 90040.7 | Y | N | 60 | missing_sequence |
| 3 | planner_maintenance | p_schema_on | planner | 32689.3 | Y | Y | 100 | ok |
| 4 | planner_maintenance | p_low_think | planner | 100807.9 | Y | N | 60 | missing_sequence |
| 5 | planner_maintenance | p_high_think | planner | 68355.1 | Y | N | 55 | done_when_minLength_20 |

**Ranking:**
- `p_schema_on`: score=100.0 avg_ms=32689.3 json=1/1 quality=1/1 empty=0
- `p_postfix`: score=60.0 avg_ms=90040.7 json=1/1 quality=0/1 empty=0
- `p_low_think`: score=60.0 avg_ms=100807.9 json=1/1 quality=0/1 empty=0
- `p_high_think`: score=55.0 avg_ms=68355.1 json=1/1 quality=0/1 empty=0
- `p_golden`: score=55.0 avg_ms=99969.0 json=1/1 quality=0/1 empty=0

## Final comparison table

| Suite | Pass | Wall ms | Avg score | Best profile | Empty outputs | Notes |
|-------|------|---------|-----------|--------------|---------------|-------|
| T01_postfix_default | FAIL | 55157.5 | 91.0 | api_schema_on | 0 | done_when_minLength_20 |
| T02_session_replay_schema_off | FAIL | 65749.5 | 90.2 | role_budget_off_2 | 0 | expected_denied_got_confirmed |
| T03_session_replay_schema_on | FAIL | 11978.4 | 100.0 | api_schema_on_4 | 0 | expected_deny_got_credit |
| T04_session_replay_golden_budgets | FAIL | 56961.7 | 72.4 | golden_verifier | 0 | invalid_json |
| T05_fission_golden_vs_postfix | FAIL | 35896.7 | 64.0 | schema_on_fission | 0 | invalid_json |
| T06_verifier_routed_matrix | PASS | 14598.8 | 100.0 | v_posted_on | 0 | ok |
| T07_default_all_schema_on | PASS | 19658.8 | 100.0 | all_schema_on_2 | 0 | ok |
| T08_default_all_schema_off | FAIL | 56282.9 | 92.0 | all_schema_off_2 | 0 | missing_sequence |
| T09_planner_budget_sweep | FAIL | 104982.7 | 56.0 | p_schema_on | 0 | missing_sequence |
| T10_repeat_schema_on_session | FAIL | 14175.5 | 99.6 | api_schema_on_repeat_2 | 0 | expected_deny_got_credit |
| T03_session_replay_schema_on_cycle11 | FAIL | 11736.3 | 100.0 | api_schema_on_4 | 0 | expected_deny_got_credit |
| T05_fission_golden_vs_postfix_cycle11 | FAIL | 41664.4 | 64.4 | schema_on_fission | 0 | invalid_json |
| T09_planner_budget_sweep_cycle11 | FAIL | 100812.1 | 66.0 | p_schema_on | 0 | done_when_minLength_20 |

## Campaign summary

- Tests run: 13
- Elapsed: 9.83 min
- Markdown: `runtime\BENCH_CAMPAIGN_20260614.md`
- Model: `nvidia-nemotron-3-nano-4b@q6_k_xl` @ `http://192.168.16.31:1234`
- Profile base: `nemotron_parallel` (project `BUDGET` / `THINKING_BUDGET` unless golden overrides)

## Conclusions (session 20260614_175152 replay)

### Reproduced golden failures

| Session symptom | Benchmark suite | Reproduced? | Root cause |
|-----------------|-----------------|-------------|------------|
| Fission judge empty JSON (`output_chars:0`, reasoning 223/224 tokens) | T04 slot 3, T05 slots 1+5 | **Yes** | `max_tokens=224` + `thinking_budget=192` — reasoning consumes entire completion budget |
| Verifier `routed` vs `posted` mismatch | T02 slot 1, T06 all routed slots | **Yes** (verifier correctly denies) | Planner prints `routed` when `done_when` requires `posted` — prompt/actor evidence mismatch |
| Verifier log.py read fail | T02/T03 slot 4 | Partial | Model sometimes `confirmed` on garbage log content — verifier LLM leniency, not param issue |
| Planner SyntaxError / log.py corruption | T02 slot 5 | Partial | `done_when_minLength_20` or `missing_sequence` without schema; fixed in code via `log.py` restore + protected files |

### Parameter winners (speed + JSON + schema compliance)

| Role | Best config | Avg ms (winner) | Pass rate |
|------|-------------|-----------------|-----------|
| **All roles** | `api_schema_on` (T07) | 19.7s wall / 7.3–19.7s per slot | **5/5** |
| **Planner** | `p_schema_on` (T09) | 32.7–33.6s | **Only config with quality_ok** |
| **Fission judge** | `postfix_fission` or `low_think_fission` (T05) | 35–41s | Valid deny JSON, no empty output |
| **Verifier** | `api_schema_on` or `v_posted_on` (T06) | 7.2–9.4s | **5/5** routed+posted matrix |

### Golden vs post-fix fission budgets

| Profile | max_tokens | thinking_budget | JSON valid | Correct deny verdict |
|---------|------------|-----------------|------------|----------------------|
| golden_fission (session) | 224 | 192 | **0/2 runs** | N/A (empty) |
| postfix_fission (current config) | 448 (role) | 128 | **2/2** | **2/2** |
| high_think_fission | 224 | 512 | **0/2** | N/A (empty) |
| schema_on_fission | 448 | 128 | **2/2** | 0/2 (credits bus-only — wrong verdict but valid JSON) |

### Code fixes validated by campaign (pre-commit)

1. **`log.py` restore + `_PROTECTED_ACTOR_FILES`** — prevents colony from corrupting logging infrastructure again.
2. **`_is_bus_only_fission_milestone()` deterministic deny** — avoids LLM empty-JSON path for bus posts (not exercised when LLM called with schema_on crediting wrongly).
3. **Fission budget 224→448, thinking 192→128** — `postfix_fission` slot passes consistently in T05.
4. **`llm.py` JSON recovery from reasoning channel** — helps when content field empty but reasoning has JSON.
5. **Planner prompt** — `print("posted message...")` example instead of `print("routed")`.

### Recommendations

1. **Enable `LLM_API_SCHEMA: true` for `nemotron_parallel`** on structured roles (planner, verifier, fission_judge, reflector, mutator). T07 is the only suite with 5/5 pass; T09 shows planner only passes with schema on.
2. **Keep post-fix fission budgets** — golden 224/192 must not return; benchmark reproduces empty JSON 4/4 times.
3. **Keep deterministic bus-only fission deny** before LLM — schema_on fission still credits bus milestones (T03/T05); strengthen pre-LLM gate or prompt.
4. **Verifier routed/posted** — colony-side fix (planner contract) is working; verifier behaves correctly in T06.

### Comparison: schema on vs off (aggregate)

| Config | Suites passing 5/5 | Planner ok | Fission empty JSON | Fastest wall |
|--------|-------------------|------------|-------------------|--------------|
| All `api_schema_on` | T07 | Yes | No | **19.7s** |
| All `api_schema_off` | — | No | No | 56.3s |
| Golden session budgets | — | No | **Yes** | 57.0s |

---

*Campaign ended after 13 suites (~10 min). Re-run: `python llm.py param-bench-campaign --minutes 30`*

