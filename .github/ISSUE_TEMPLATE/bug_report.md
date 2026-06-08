---
name: Bug Report
about: Report a runtime failure or unexpected behavior
title: '[BUG] '
labels: bug
assignees: ''
---

## What happened

Describe the failure.

## Goal used

The exact raw goal string passed to main.py. Runtime logs should also show the wrapped goal and `original_goal`.

## Backend

- [ ] acp (Claude via kiro-cli)
- [ ] lmstudio (local model)

If lmstudio: which model?

## Environment

- OS: Windows 11
- Python: 3.13
- Run as Administrator: yes/no

## Stagnation state at failure

- stagnation_score:
- pid_output:
- iteration:
- consecutive_failures:

## Log file

Paste relevant JSON events from `log-*.txt` or `blackboard_events.txt`, or attach the file.

## Steps to reproduce

1. `python main.py "goal" --backend X`
2. What happened

## Expected behavior

What should have happened instead.
