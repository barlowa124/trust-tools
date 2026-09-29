# Trajectory audit report

- Session: `dazed-tachometer`
- Events: 476 (89 assistant, 191 tool_call, 190 tool_result, 6 user)
- Findings: 2

| Detector | Findings |
|---|---|
| `verification_claim_gap` | 1 |
| `completion_without_verification` | 0 |
| `abandoned_items` | 0 |
| `plan_drift` | 0 |
| `scope_drift` | 0 |
| `unplanned_work` | 1 |

Findings are deterministic heuristics, not verdicts. Each links to
event indices (`event_i`) in the trajectory for human review.

## Findings

- **[low]** `unplanned_work` @ event 0: 191 tool calls with no plan event in the session
- **[high]** `verification_claim_gap` @ event 0: 'test' claim with no matching command anywhere earlier in the trajectory
  - `trust_hardened_diagram.py` All 220 QMS tests passed after generator synchronization. #### Tokyo/Mexico manor research `~/CascadeP`
