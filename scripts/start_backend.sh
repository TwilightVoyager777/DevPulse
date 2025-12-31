#!/usr/bin/env bash
# ── DevPulse Backend Starter ──────────────────────────────────────────────────
# Generates JWT keys on first run, then starts Spring Boot.
# Usage: bash scripts/start_backend.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
KEYS_DIR="$ROOT_DIR/.keys"

cd "$ROOT_DIR/backend"

# ── 1. Generate RSA keys (only once) ─────────────────────────────────────────
if [ ! -f "$KEYS_DIR/private.pem" ]; then
  echo "Generating RSA-2048 key pair..."
  mkdir -p "$KEYS_DIR"
  openssl genrsa -out "$KEYS_DIR/private.pem" 2048 2>/dev/null
  openssl rsa -in "$KEYS_DIR/private.pem" -pubout -out "$KEYS_DIR/public.pem" 2>/dev/null
  echo "Keys saved to .keys/ (git-ignored)"
fi

# ── 2. Export all required env vars ──────────────────────────────────────────
export SPRING_DATASOURCE_URL="jdbc:postgresql://localhost:5432/devpulse"
export POSTGRES_USER="devpulse"
export POSTGRES_PASSWORD="devpulse_secret"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export JWT_PRIVATE_KEY="$(cat "$KEYS_DIR/private.pem")"
export JWT_PUBLIC_KEY="$(cat "$KEYS_DIR/public.pem")"
export JWT_EXPIRY_MINUTES="15"
export JWT_REFRESH_EXPIRY_DAYS="7"

echo "Starting Spring Boot backend..."
./gradlew bootRun
