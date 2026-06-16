"""Minimal LLM prompt benchmark for the contract-bus circuits."""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "planner_contract_bus_task",
        "role": "planner",
        "system": "Return contract-bus task and contract records only.",
        "user": "ROOT_TASK_ID: root-1\nACTIVE_TASK: Create one verifiable local maintenance subtask.\nPlanner JSON:",
    },
    {
        "name": "actor_claim_only_done",
        "role": "actor",
        "system": "Return actor JSON. DONE is only a claim.",
        "user": "INSTRUCTION: The active contract appears complete from the screen.\nSCREEN:\n[1] Text \"ready\"\nJSON:",
    },
    {
        "name": "verifier_unknown_without_evidence",
        "role": "verifier",
        "system": "Verify one active task from a verification-packet.v1 and return Verdict data.",
        "user": json.dumps({
            "schema_version": "verification-packet.v1",
            "root_task": {"id": "root-1", "description": "context"},
            "active_task": {"id": "task-1", "description": "produce an artifact", "contract_id": "contract-1", "status": "claimed_done"},
            "active_contract": {
                "id": "contract-1",
                "task_id": "task-1",
                "version": 1,
                "done_when": "artifact exists and was read back",
                "success_conditions": [{"id": "sc-1", "description": "artifact exists and was read back", "required": True,
                    "proof_requirement": {"required_evidence_classes": ["external_readback"], "min_independent_sources": 1,
                    "actor_claim_allowed_as_primary": False, "allow_inference": False, "max_age_cycles": 3}}],
                "forbidden_primary_evidence_classes": ["actor_self_report", "keyword_match_only", "planner_intent_only"],
                "uncertainty_policy": {"missing_required_evidence": "UNKNOWN", "contradictory_evidence": "NOT_DONE", "stale_evidence": "UNKNOWN"},
            },
            "records": {"actions": [], "evidence": [], "claims": [{"record_type": "claim", "data": {"source_class": "actor_self_report"}}], "prior_verdicts": [], "runtime_events": []},
            "verifier_capability": {"role": "verifier", "can_verify": True, "can_publish_verdict": True},
        }),
    },
]


def _body(scenario: dict[str, Any], temperature: float, max_tokens: int) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": scenario["system"]},
            {"role": "user", "content": scenario["user"]},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def _run_one(scenario: dict[str, Any], host: str, temperature: float, max_tokens: int, timeout: int) -> dict[str, Any]:
    started = time.time()
    req = urllib.request.Request(
        f"{host}/v1/chat/completions",
        data=json.dumps(_body(scenario, temperature, max_tokens), ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"name": scenario["name"], "ok": True, "latency_ms": int((time.time() - started) * 1000), "content": content}
    except Exception as exc:
        return {"name": scenario["name"], "ok": False, "latency_ms": int((time.time() - started) * 1000), "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Contract-bus LLM prompt benchmark")
    parser.add_argument("--host", default="http://localhost:1234")
    parser.add_argument("--temperature", type=float, default=0.12)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--concurrent", type=int, default=1)
    args = parser.parse_args()

    with ThreadPoolExecutor(max_workers=args.concurrent) as pool:
        futures = [pool.submit(_run_one, s, args.host, args.temperature, args.max_tokens, args.timeout) for s in SCENARIOS]
        for fut in as_completed(futures):
            result = fut.result()
            status = "OK" if result["ok"] else "XX"
            print(f"{status} {result['name']} {result['latency_ms']}ms {(result.get('content') or result.get('error', ''))[:100]}")


if __name__ == "__main__":
    main()
