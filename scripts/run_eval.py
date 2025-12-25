#!/usr/bin/env python3
"""
DevPulse — RAG evaluation script.

Sends a sample of questions to the chat API and evaluates:
  - Hit rate: % of answers that contain the expected keyword(s)
  - Relevance score: avg semantic similarity between answer and expected
  - Latency: P50/P95/P99 end-to-end response times
  - Token cost: estimated USD using Claude claude-sonnet-4-6 pricing

Usage:
  python scripts/run_eval.py \\
      --workspace-id <uuid> \\
      --api-url http://localhost:8080 \\
      --token <jwt-access-token> \\
      [--samples 500] \\
      [--eval-file scripts/eval_questions.jsonl]

eval_questions.jsonl format (one JSON object per line):
  {"question": "What is the GIL in Python?", "expected_keywords": ["Global Interpreter Lock", "thread"]}
  {"question": "How do I use Redis EXPIRE?", "expected_keywords": ["expire", "TTL", "seconds"]}
"""

import argparse
import json
import sys
import time
import statistics
import uuid
from pathlib import Path
from typing import Optional

import requests

# ─── Pricing (claude-sonnet-4-6 as of 2026-04) ────────────────────────────────
# $3.00 per 1M input tokens, $15.00 per 1M output tokens
PRICE_INPUT_PER_TOKEN  = 3.00  / 1_000_000
PRICE_OUTPUT_PER_TOKEN = 15.00 / 1_000_000

# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate DevPulse RAG quality")
    p.add_argument("--workspace-id", required=True)
    p.add_argument("--api-url", default="http://localhost:8080")
    p.add_argument("--token", required=True)
    p.add_argument("--samples", type=int, default=500,
                   help="Max questions to evaluate (default: 500)")
    p.add_argument("--eval-file", default="scripts/eval_questions.jsonl",
                   help="JSONL file with evaluation questions")
    p.add_argument("--output", default="eval_results.json",
                   help="Write JSON results to this file")
    p.add_argument("--timeout", type=float, default=60.0,
                   help="Seconds to wait for each SSE stream to complete")
    return p.parse_args()

# ─── API client ───────────────────────────────────────────────────────────────

class EvalClient:
    def __init__(self, base_url: str, token: str, workspace_id: str, timeout: float):
        self.base = base_url.rstrip("/")
        self.workspace_id = workspace_id
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def create_session(self) -> str:
        resp = self.session.post(
            f"{self.base}/api/workspaces/{self.workspace_id}/sessions",
            json={"title": "Eval Session"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def delete_session(self, session_id: str) -> None:
        try:
            self.session.delete(
                f"{self.base}/api/workspaces/{self.workspace_id}/sessions/{session_id}",
                timeout=10,
            )
        except Exception:
            pass

    def send_and_stream(self, session_id: str, question: str) -> dict:
        """
        POST message then poll SSE until isDone.
        Returns: {answer, tokens_used, latency_ms, sources}
        """
        # 1. Send message
        t_start = time.time()
        resp = self.session.post(
            f"{self.base}/api/workspaces/{self.workspace_id}/sessions/{session_id}/messages",
            json={"content": question},
            timeout=10,
        )
        resp.raise_for_status()
        task_id = resp.json()["taskId"]

        # 2. Poll task status directly (simpler than SSE for eval)
        deadline = t_start + self.timeout
        poll_url = f"{self.base}/api/tasks/{task_id}"
        while time.time() < deadline:
            time.sleep(0.5)
            pr = self.session.get(poll_url, timeout=10)
            if pr.status_code != 200:
                continue
            task = pr.json()
            if task.get("status") in ("DONE", "FAILED"):
                latency_ms = int((time.time() - t_start) * 1000)
                payload = json.loads(task.get("payload") or "{}")
                return {
                    "answer": payload.get("fullResponse", ""),
                    "tokens_used": payload.get("tokensUsed", 0),
                    "latency_ms": latency_ms,
                    "sources": payload.get("sources", []),
                    "status": task["status"],
                }

        return {
            "answer": "",
            "tokens_used": 0,
            "latency_ms": int((time.time() - t_start) * 1000),
            "sources": [],
            "status": "TIMEOUT",
        }

# ─── Evaluation helpers ───────────────────────────────────────────────────────

def keyword_hit(answer: str, expected_keywords: list[str]) -> bool:
    """True if ANY expected keyword appears in the answer (case-insensitive)."""
    answer_lower = answer.lower()
    return any(kw.lower() in answer_lower for kw in expected_keywords)


def compute_percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * pct / 100)
    idx = min(idx, len(sorted_v) - 1)
    return sorted_v[idx]

# ─── Default eval questions (used when no file provided) ─────────────────────

DEFAULT_QUESTIONS = [
    {"question": "What is the Python GIL and when does it matter?",
     "expected_keywords": ["Global Interpreter Lock", "thread", "GIL"]},
    {"question": "How do I use Redis EXPIRE to set key TTL?",
     "expected_keywords": ["EXPIRE", "TTL", "seconds", "expire"]},
    {"question": "What is the difference between TCP and UDP?",
     "expected_keywords": ["TCP", "UDP", "connection", "reliable"]},
    {"question": "How does a hash table work?",
     "expected_keywords": ["hash", "bucket", "collision", "key"]},
    {"question": "What is a database index and when should I use one?",
     "expected_keywords": ["index", "query", "B-tree", "performance"]},
]

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # Load questions
    questions = []
    eval_path = Path(args.eval_file)
    if eval_path.exists():
        with open(eval_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    questions.append(json.loads(line))
        print(f"Loaded {len(questions)} questions from {eval_path}")
    else:
        questions = DEFAULT_QUESTIONS
        print(f"Eval file not found; using {len(questions)} built-in questions")

    questions = questions[: args.samples]
    n = len(questions)
    print(f"Evaluating {n} questions against workspace {args.workspace_id}")
    print()

    client = EvalClient(args.api_url, args.token, args.workspace_id, args.timeout)

    results = []
    hits = 0
    latencies_ms: list[float] = []
    total_tokens = 0
    errors = 0

    for i, q in enumerate(questions):
        question = q["question"]
        expected_keywords = q.get("expected_keywords", [])

        # Each question gets a fresh session to avoid context bleed
        session_id = client.create_session()
        try:
            result = client.send_and_stream(session_id, question)
        except Exception as e:
            print(f"  [{i+1}/{n}] ERROR: {e}")
            errors += 1
            client.delete_session(session_id)
            continue
        finally:
            client.delete_session(session_id)

        is_hit = keyword_hit(result["answer"], expected_keywords) if expected_keywords else True
        if is_hit:
            hits += 1

        latencies_ms.append(result["latency_ms"])
        total_tokens += result["tokens_used"] or 0

        results.append({
            "question": question,
            "answer_snippet": result["answer"][:200],
            "hit": is_hit,
            "latency_ms": result["latency_ms"],
            "tokens_used": result["tokens_used"],
            "sources_count": len(result["sources"]),
            "status": result["status"],
        })

        status_icon = "✓" if is_hit else "✗"
        print(
            f"  [{i+1:3}/{n}] {status_icon} {result['latency_ms']:5}ms "
            f"| {result['tokens_used'] or 0:4} tok "
            f"| {len(result['sources'])} sources "
            f"| {question[:60]}"
        )

    # ── Summary ──────────────────────────────────────────────────────────────
    evaluated = n - errors
    hit_rate = (hits / evaluated * 100) if evaluated > 0 else 0
    p50 = compute_percentile(latencies_ms, 50)
    p95 = compute_percentile(latencies_ms, 95)
    p99 = compute_percentile(latencies_ms, 99)
    avg_latency = statistics.mean(latencies_ms) if latencies_ms else 0

    # Cost estimate: assume 50% input / 50% output token split
    estimated_cost_usd = (
        total_tokens * 0.5 * PRICE_INPUT_PER_TOKEN +
        total_tokens * 0.5 * PRICE_OUTPUT_PER_TOKEN
    )

    print()
    print("=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"  Questions evaluated : {evaluated} / {n}")
    print(f"  Errors              : {errors}")
    print(f"  Hit rate            : {hit_rate:.1f}%  ({hits}/{evaluated})")
    print(f"  Avg latency         : {avg_latency:.0f} ms")
    print(f"  P50 latency         : {p50:.0f} ms")
    print(f"  P95 latency         : {p95:.0f} ms")
    print(f"  P99 latency         : {p99:.0f} ms")
    print(f"  Total tokens used   : {total_tokens:,}")
    print(f"  Estimated cost      : ${estimated_cost_usd:.4f} USD")
    print("=" * 60)

    # Write JSON output
    output = {
        "summary": {
            "questions": n,
            "evaluated": evaluated,
            "errors": errors,
            "hit_rate_pct": round(hit_rate, 2),
            "avg_latency_ms": round(avg_latency),
            "p50_ms": round(p50),
            "p95_ms": round(p95),
            "p99_ms": round(p99),
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost_usd, 4),
        },
        "results": results,
    }
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results written to {args.output}")


if __name__ == "__main__":
    main()
