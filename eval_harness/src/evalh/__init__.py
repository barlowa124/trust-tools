"""evalh: provenance-bound evaluation harness.

Task spec -> deterministic graders -> hash-chained result records.
Every run is replay-verifiable: the task spec, model identity, and each
output are bound by sha256 and linked in order.
"""

from .runner import run, check_log, summarize
from .tasks import load_tasks

__all__ = ["run", "check_log", "summarize", "load_tasks"]
