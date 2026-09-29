"""receipt_report: audit documents generated from receipt chains.

Reads the hash-chained records produced by the sibling trust-tools
packages — evalh `eval_result` logs, modelserve `serve_response` logs,
llmreceipt inference receipts — verifies each chain, then renders a
markdown evaluation/audit report whose every number traces to records a
reviewer can re-verify.

The report states what the evidence does and does not cover. It never
upgrades local results into capability or safety claims.
"""
