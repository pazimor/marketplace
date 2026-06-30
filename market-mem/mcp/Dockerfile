FROM python:3.12-slim

WORKDIR /app

# System deps for tree-sitter native builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install torch CPU-only first (much smaller than the default CUDA build)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

# Optional Tier 2/3 language parsers — versioning varies, install best-effort.
# Missing packages are gracefully degraded in graph_builder.py (_try_import).
RUN pip install --no-cache-dir tree-sitter-swift tree-sitter-scala \
      tree-sitter-haskell tree-sitter-elixir 2>/dev/null || true

COPY server/ ./server/

EXPOSE 7333

CMD ["python", "-m", "server.main"]
