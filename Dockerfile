# Stage 1: build the frontend
FROM node:22-slim AS web
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# Stage 2: python runtime serving API + built UI from one image
FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/askrepo_live ./askrepo_live
COPY --from=web /app/dist ./static
# no LM Studio in prod — query embeddings must match the Voyage-built index
ENV STATIC_DIR=/app/static AMR_PREFER_LOCAL=0
EXPOSE 8080
CMD ["sh", "-c", "uvicorn askrepo_live.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
