FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY oncocs ./oncocs
COPY cohorts ./cohorts

RUN pip install --no-cache-dir .

# Results/data/splits/rag corpus are provided at runtime, not baked in:
#   docker run -v /path/to/repo/results:/app/results -p 8000:8000 oncocs
# The LLM backend (Ollama) is NOT in this image; the API serves saved runs
# and human review only.
VOLUME ["/app/results", "/app/data", "/app/splits", "/app/rag"]

EXPOSE 8000
CMD ["python", "-m", "oncocs", "serve", "--host", "0.0.0.0", "--port", "8000"]
