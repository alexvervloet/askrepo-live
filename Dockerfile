# Stage 1: build the frontend
FROM node:22-slim AS web
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# Stage 2: build python wheels. Needs git because ask-my-repo is pinned as a
# git requirement; keeping git out of the runtime stage keeps the image lean.
FROM python:3.13-slim AS wheels
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Stage 3: python runtime serving API + built UI from one image
FROM python:3.13-slim
WORKDIR /app
COPY --from=wheels /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
COPY backend/askrepo_live ./askrepo_live
COPY --from=web /app/dist ./static
# no LM Studio in prod: query embeddings must match the Voyage-built index
ENV STATIC_DIR=/app/static AMR_PREFER_LOCAL=0 TRUST_PROXY=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8080\")}/healthz')"
CMD ["sh", "-c", "uvicorn askrepo_live.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
