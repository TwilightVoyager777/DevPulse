#!/usr/bin/env bash
# ── DevPulse AI Worker Starter ────────────────────────────────────────────────
# Sets all env vars and starts the FastAPI AI worker.
# Usage: bash scripts/start_ai_worker.sh
# Requires: ANTHROPIC_API_KEY to be set beforehand, or edit this file.
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR/ai-worker"

# ── Check ANTHROPIC_API_KEY ───────────────────────────────────────────────────
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set."
  echo "Run: export ANTHROPIC_API_KEY=sk-ant-..."
  exit 1
fi

# ── Export all required env vars ─────────────────────────────────────────────
export DATABASE_URL="postgresql://devpulse:devpulse_secret@localhost:5432/devpulse"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export EMBEDDING_MODEL="all-MiniLM-L6-v2"
export LOG_LEVEL="INFO"

echo "Starting AI Worker..."
uvicorn app.main:app --reload --port 8000
