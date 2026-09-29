# model_serve

A model-serving slice: queueing, micro-batching, shadow comparison, and
a hash-bound record for every response.

`Service` owns a production `generate_fn` and an optional shadow
candidate. Requests queue; the drain loop batches up to `batch_size` or
`batch_window_s`. Each response record carries input/output hashes,
queue and serve latency, the batch's model identity, optional shadow
output and agreement flag, and `chain_prev` — the same canonical
envelope as inference_receipts and evalh, so the logs interoperate.

Shadow mode runs the candidate on `shadow_fraction` of traffic and
records whether outputs agree with primary. Divergence is data: it lands
in the record and the shadow report, not an error path.

```
modelserve serve --model-dir CKPT [--shadow-dir CAND --shadow-fraction 0.1]
modelserve replay --prompts prompts.txt --model-dir CKPT --out run.jsonl
modelserve verify run.jsonl
```

The core is stdlib-only with injectable `generate_fn`; FastAPI/uvicorn
and transformers are optional extras (`pip install .[api,hf]`).

Limits: in-process queue, single worker — this demonstrates serving
mechanics (batching, shadow eval, receipt binding), not a production
inference stack.
