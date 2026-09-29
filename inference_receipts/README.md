# inference-receipts

Hash-bound, replayable receipts for LLM calls. `llmreceipt` runs a
generation, records the exact weights hash, the input text, the generation
settings, the output text, and the hash of the previous receipt in the
log. Verification is recomputation. Re-hash the record, re-walk the
chain, and optionally re-run the generation to compare output hashes.

The committed example (`examples/receipts/smollm2_chain.jsonl`) is two real
calls to `HuggingFaceTB/SmolLM2-135M` on CPU, greedy decoding. Both replay
bit-exact (`replay=verified`). `tampered_chain.jsonl` is the same log with
one output edited. `verify` flags it from both the content hash and the
output hash before any replay runs.

## What a receipt proves, and what it does not

A verified replay establishes a narrow, checkable claim. **On the recorded
backend configuration, this exact input to these exact weights produced
this exact output.** That is a provenance statement about one computation,
not a statement about whether the model is right on
other inputs.

- It does **not** prove the output is true or safe.
- It does **not** generalize across backends. A mismatch replayed under
  different torch/transformers versions or different hardware is a
  characterization result (plausible nondeterminism source), not proof of
  tampering. Bit-exact replay is claimed only for the recorded config
  (HF transformers, CPU, float32, greedy decoding).
- It does **not** cover server-side inference. There is no way to recompute
  a closed API's forward pass. This tool exists for local/open-weight
  inference where replay is possible.
- The hash chain proves the log was not edited *after the fact*. It does
  not prove the recorder ran the calls honestly in the first place. That
  part still requires trusting or re-running the capture.

## Receipt schema

```json
{
  "v": 1,
  "receipt_id": "rcpt-<sha256[:16] of canonical body>",
  "created_at": "iso8601",
  "chain_prev": "rcpt-<id> | genesis",
  "backend": {"kind": "hf-transformers", "transformers": "...",
              "torch": "...", "device": "cpu", "dtype": "float32"},
  "model": {"id": "HuggingFaceTB/SmolLM2-135M", "revision": "...",
            "weights_sha256": "<sha256 over all weight files, sorted>"},
  "input": {"text": "...", "sha256": "..."},
  "generation": {"do_sample": false, "temperature": 0.0,
                 "max_new_tokens": 24},
  "output": {"text": "...", "sha256": "...",
             "n_new_tokens": 24, "gen_time_s": 1.23},
  "replay": {"status": "pending|verified|mismatch",
             "output_sha256_on_replay": "...", "replay_backend": {...}}
}
```

`receipt_id` is the hash of the whole body, so any edit to any field
breaks it. `chain_prev` makes reordering or dropping receipts detectable.

## Usage

```bash
pip install -e ".[hf]"

# Run a generation and append its receipt to a log
llmreceipt capture --model HuggingFaceTB/SmolLM2-135M \
    --prompt "Question: ...? Answer:" --out receipts.jsonl

# Check integrity and hash chain (no model needed)
llmreceipt verify receipts.jsonl

# Re-run each generation and compare output hashes (needs the model)
llmreceipt verify receipts.jsonl --replay

# Inspect one receipt
llmreceipt show receipts.jsonl rcpt-<id>
```

## Verification semantics

| Check | Needs model? | Detects |
|---|---|---|
| Content hash vs `receipt_id` | no | Any edit to the receipt body |
| `input`/`output` hash vs text | no | Edited prompts or outputs |
| `chain_prev` links | no | Reordered, dropped, or spliced receipts |
| Live replay (`--replay`) | yes | Recorded output that doesn't match what the model actually produces |

## Development

```bash
python -m pytest tests/ -q    # 8 tests; receipt/chain/tamper logic, no downloads
```

MIT license.
