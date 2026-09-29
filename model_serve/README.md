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
modelserve bench --model-dir CKPT --batch-sizes 1,4,8 --requests 60 \
    --concurrency 8 --out bench.json
```

## Benchmark

`bench` drives `n_requests` through `concurrency` client threads and
reports client wall latency, queue wait, and generation time as
percentiles. Throughput and chain integrity land in the same report.
The committed run
(`results/bench_smollm2_sft.json`) is 60 requests against a SmolLM2-135M
checkpoint on CPU, batch sizes 1/4/8.

The measurement doubles as a caveat. `Service._serve_batch` collects
requests into batches but still calls `generate_fn` once per request.
Batching adds queue wait without fused compute, and whether it nets a
win flips between runs on a laptop CPU (the committed sweep has batch 8
at 2.0 rps vs 1.1 for batch 1. An earlier run ranked them the other
way). A batched tensor-call backend is the change that would make the
throughput claim real, and it does not exist yet.

The core is stdlib-only with injectable `generate_fn`; FastAPI/uvicorn
and transformers are optional extras (`pip install .[api,hf]`).

Limits: in-process queue, single worker. This demonstrates serving
mechanics (batching, shadow eval, receipt binding), not a production
inference stack. The bench numbers measure this layer on CPU, not
datacenter throughput.
