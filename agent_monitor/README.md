# agent_monitor

Pre-execution policy gate for agent tool calls *and* emitted answers.
The trajectory audit moved upstream, on both sides of the loop.

`trajaudit` reviews a finished session. `agentmon` sits in the loop:
each tool call is checked against an explicit policy before it lands,
and each emitted answer is checked before it leaves. Every decision
(`allow`, `flag`, or `block`) becomes a hash-chained event record
carrying the matched rule, the severity, and a content hash. The log
verifies the same way as the sibling packages' chains.

Policies are data (`policies/default.json`). `rules` run over the tool
call: its name, its argument patterns, its path prefixes.
`output_rules` run over the emitted answer. A rule can match a write
tool's target path, an exec command's substring, or any argument value.
An output rule can match secret-shaped strings, enforce a JSON format
and field contract, require a citation pattern, or cap answer length.
Unmatched calls and answers fall through to the policy's default
action.

```python
from agentmon.monitor import Monitor
from agentmon.policy import load_policy

mon = Monitor(load_policy("policies/default.json"))
decision = mon.check(tool="write", args={"file_path": "/etc/hosts"})
# decision.action == "deny"; record appended to mon.records

answer = mon.check_output("the key is sk-aB3xK9...")
# answer.action == "deny" (credential-shaped string)
```

`gate` and `gate_output` enforce instead of just evaluating: a deny
raises `DenyError` before the call runs or the answer ships. `wrap`
decorates tool functions. `wrap_output` decorates the emission seam.

What it does not catch. The monitor sees what the call *says*, not what
it *does*. A path can be symlinked, a command's effect can differ from
its text, and a policy that never mentions a tool lets it through by
default. On the output side, regex catches *known* token shapes. An
encoded or reworded secret has no shape to match. The false-negative
surface is measured rather than asserted. The `redteam` battery attacks
both gates and reports evasions openly (`agentmon redteam`).
