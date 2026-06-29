FROM python:3.12-slim

WORKDIR /app

# System deps for tree-sitter native builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/

EXPOSE 7333

CMD ["python", "-m", "server.main"]
