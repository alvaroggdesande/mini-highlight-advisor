# Stage 1: build the React SPA
FROM node:20-alpine AS frontend
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python runtime + built SPA
FROM python:3.11-slim AS runtime
WORKDIR /app

# OpenCV headless runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
  && rm -rf /var/lib/apt/lists/*

# Python deps (no streamlit in prod)
RUN pip install --no-cache-dir \
    numpy \
    opencv-python-headless \
    pillow \
    fastapi \
    "uvicorn[standard]" \
    python-multipart

# Application source (src/ on PYTHONPATH — no install needed, data files preserved)
COPY src/ ./src/
COPY backend/ ./backend/

# Built frontend assets (served by FastAPI at / in prod)
COPY --from=frontend /app/web/dist ./web/dist

ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
