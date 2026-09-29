# agent_monitor

Pre-execution policy gate for agent tool calls — the trajectory audit
moved upstream.

`trajaudit` reviews a finished session; `agentmon` sits in the loop.
Each tool call is checked against an explicit policy before it lands,
and the decision — `allow`, `flag`, or `block` — is emitted as a
hash-chained event record carrying the matched rule, severity, and call
hash. The log verifies the same way as the sibling packages' chains.

Policies are data (`policies/default.json`): ordered rules over tool
name, argument patterns, and path prefixes. A rule can match a write
tool's target path, an exec command's substring, or any argument value.
Unmatched calls fall through to the policy's default action.

```python
from agentmon.monitor import Monitor
from agentmon.policy import load_policy

mon = Monitor(load_policy("policies/default.json"))
decision = mon.check(tool="write", args={"file_path": "/etc/hosts"})
# decision.action == "block"; record appended to mon.records
```

What it does not catch: the monitor sees what the call *says*, not what
it *does* — a path can be symlinked, a command's effect can differ from
its text, and a policy that never mentions a tool lets it through by
default. The false-negative surface is measured, not asserted:
`agent_trajectory_audit`'s `redteam` battery attacks detectors of this
same shape and reports evasions openly.
