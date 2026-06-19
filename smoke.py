"""Smoke suite entry point — delegates to wiring.suites.smoke chain."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wiring import load_wiring, run_suite

BASE_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = BASE_DIR / "prompts"


def main() -> int:
    parser = argparse.ArgumentParser(prog="smoke", description="Run wiring.suites.smoke cognitive probes")
    parser.add_argument("--id", help="Run single scenario id (e.g. s01)")
    parser.add_argument("--responses", type=int, help="Override suite default response_limit")
    parser.add_argument("--desktop", action="store_true", help="Enable desktop observation")
    args = parser.parse_args()

    wiring = load_wiring(PROMPTS_DIR)
    defaults = wiring.get("suites", {}).get("smoke", {}).get("defaults", {})
    limit = args.responses if args.responses is not None else int(defaults.get("response_limit", 1))
    no_desktop = not args.desktop and bool(defaults.get("no_desktop", True))

    report = run_suite(
        "smoke",
        prompts_dir=PROMPTS_DIR,
        workspace=BASE_DIR,
        scenario_id=args.id,
        response_limit=limit,
        no_desktop=no_desktop,
    )
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())