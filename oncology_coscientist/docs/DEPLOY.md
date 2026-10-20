# Deploying oncocs

The service runs as two containers, the FastAPI app and Postgres. The model
is a third, separate thing that lives wherever you can run it. A Colab
GPU session, a self-hosted server, or a hosted API all work. The app
only needs an OpenAI-compatible URL.

## docker compose

```bash
cd web && npm install && npm run build && cd ..
docker compose up --build
```

- API: http://localhost:8000 (OpenAPI docs at /docs)
- UI: http://localhost:8000/ui (the Dockerfile's node stage builds it,
  or the local `npm run build` above when developing)

Postgres holds the `agent_runs` and `jobs` tables (`oncocs/store.py`,
the schema is created on first connect). Agent-run records are
upserted when a triggered run finishes and on every approve/reject,
so the deployed reads come from Postgres while `results/` stays the
canonical record on disk.

## The model lives elsewhere

`EndpointBackend` calls `POST {ONCOCS_LLM_BASE_URL}/chat/completions`
with the standard OpenAI body. Anything that speaks that protocol
works:

- **Colab**: run vLLM (`python -m vllm.entrypoints.openai.api_server
  --model google/gemma-3-4b-it`) or Ollama on the free T4, then expose
  port 8000 with a tunnel (`cloudflared tunnel --url localhost:8000` or
  ngrok). Put the tunnel URL in `ONCOCS_LLM_BASE_URL` including the
  `/v1` suffix.
- **Self-hosted**: llama.cpp's `llama-server`, text-generation-webui,
  and Ollama's `/v1` compatibility mode all work the same way.
- **Hosted**: any OpenAI-compatible provider. Set
  `ONCOCS_LLM_API_KEY` as well.

```bash
export ONCOCS_LLM_BASE_URL=https://your-tunnel-host.example/v1
export ONCOCS_LLM_MODEL=google/gemma-3-4b-it
export ONCOCS_LLM_API_KEY=optional-bearer
```

Colab free tier sleeps and tunnels expire, so expect to refresh the
URL when the session restarts. That is a demo-endpoint constraint, not
a code path.

## Triggering a run

```bash
curl -X POST http://localhost:8000/runs/LUAD/<run_id>/agent \
  -H 'Content-Type: application/json' \
  -d '{"backend": "endpoint"}'
# {"job_id": "...", "status": "running"}
curl http://localhost:8000/jobs/<job_id>
```

`backend` is one of `endpoint` (env-configured, the deployed path),
`ollama` (local dev), or `scripted-demo` (deterministic responses built
from the real results, so the pipeline runs end-to-end offline and in
CI without a model.)

## What this does not do

- No auth on the API. The human-review endpoints are meant for a
  single-operator deployment or behind your platform's auth.
- Postgres mirrors runs. It does not compute anything. The verifier
  still runs in-process on every draft.
- A triggered run reuses the recorded pipeline inputs. It cannot
  recompute survival results, only re-draft the report over saved
  results.json files.
