# ── Stage 1: Dependencies ─────────────────────────────────────────────────────
FROM python:3.11-slim AS deps
WORKDIR /app

RUN pip install --upgrade pip
COPY requirements.txt .
# Pre-download sentence-transformers model weights into image
RUN pip install --no-cache-dir -r requirements.txt && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

RUN addgroup --system devpulse && adduser --system --ingroup devpulse devpulse

# Copy installed packages and model cache
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY --from=deps /root/.cache /home/devpulse/.cache

COPY app ./app

RUN chown -R devpulse:devpulse /app /home/devpulse/.cache
USER devpulse

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
