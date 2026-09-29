"""agentmon: policy-driven live interception of agent tool calls.

Post-hoc audit sees what happened; this is the in-line version — a gate
that evaluates each tool call against a policy before it runs, emitting a
hash-chained alert record for anything it flags or denies.
"""

from .monitor import DenyError, Monitor, check_log
from .policy import evaluate, load_policy

__all__ = ["Monitor", "DenyError", "check_log", "evaluate", "load_policy"]
