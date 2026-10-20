FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# scikit-survival and ecos ship x86_64 wheels only; on aarch64 they
# build from source and need a compiler.
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc g++ \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY oncocs ./oncocs
COPY cohorts ./cohorts
COPY --from=web /web/dist ./web/dist

RUN pip install --no-cache-dir .[deploy]

# Results/data/splits/rag corpus are provided at runtime, not baked in:
#   docker run -v /path/to/repo/results:/app/results -p 8000:8000 oncocs
# The LLM backend is NOT in this image — the model lives behind
# ONCOCS_LLM_BASE_URL (any OpenAI-compatible endpoint). Without it the
# API still serves saved runs and scripted-demo agent runs.
VOLUME ["/app/results", "/app/data", "/app/splits", "/app/rag"]

EXPOSE 8000
CMD ["python", "-m", "oncocs", "serve", "--host", "0.0.0.0", "--port", "8000"]
