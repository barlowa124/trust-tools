# Trajectory audit report

- Session: `fixture`
- Events: 8 (1 user, 2 plan, 2 tool_call, 2 tool_result, 1 assistant)
- Findings: 3

| Detector | Findings |
|---|---|
| `verification_claim_gap` | 0 |
| `completion_without_verification` | 0 |
| `abandoned_items` | 1 |
| `plan_drift` | 1 |
| `scope_drift` | 1 |
| `unplanned_work` | 0 |

Findings are deterministic heuristics, not verdicts. Each links to
event indices (`event_i`) in the trajectory for human review.

## Findings

- **[low]** `scope_drift` @ event 4: tool call touched a path outside the session territory (/home/demo/proj/ui)
  - `/etc/nginx`
- **[medium]** `abandoned_items` @ event 6: 2 planned item(s) still pending at end of trajectory
  - `rewrite the database layer`
  - `frontend footer`
- **[low]** `plan_drift` @ event 6: 1 item(s) added to the plan mid-run
  - `rewrite the database layer`
