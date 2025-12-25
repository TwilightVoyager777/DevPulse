#!/usr/bin/env python3
"""
DevPulse — Stack Overflow data seeder.

Parses a Stack Overflow Posts.xml dump and imports questions + accepted answers
as documents into a DevPulse workspace via the REST API.

Usage:
  python scripts/seed_data.py \\
      --workspace-id <uuid> \\
      --input /path/to/Posts.xml \\
      --api-url http://localhost:8080 \\
      --token <jwt-access-token> \\
      [--limit 50000] \\
      [--resume]

Stack Overflow data dump: https://archive.org/details/stackexchange
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed DevPulse with SO posts")
    p.add_argument("--workspace-id", required=True, help="DevPulse workspace UUID")
    p.add_argument("--input", required=True, help="Path to Stack Overflow Posts.xml")
    p.add_argument("--api-url", default="http://localhost:8080", help="Backend base URL")
    p.add_argument("--token", required=True, help="JWT access token")
    p.add_argument("--limit", type=int, default=50_000, help="Max documents to import")
    p.add_argument("--resume", action="store_true", help="Skip already-imported document IDs")
    p.add_argument("--batch-delay", type=float, default=0.05, help="Seconds between API calls")
    p.add_argument("--progress-file", default=".seed_progress.json",
                   help="JSON file tracking import state")
    return p.parse_args()

# ─── Progress tracking ────────────────────────────────────────────────────────

def load_progress(path: str) -> set:
    try:
        with open(path) as f:
            return set(json.load(f).get("imported_ids", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_progress(path: str, imported_ids: set) -> None:
    with open(path, "w") as f:
        json.dump({"imported_ids": list(imported_ids)}, f)

# ─── XML parsing ─────────────────────────────────────────────────────────────

def parse_posts(xml_path: str):
    """
    Yield (question_id, title, body) tuples for PostTypeId=1 (questions).
    Skips posts without a Title (usually deleted/merged posts).
    """
    context = ET.iterparse(xml_path, events=("start",))
    for _event, elem in context:
        if elem.tag != "row":
            continue
        if elem.attrib.get("PostTypeId") != "1":
            elem.clear()
            continue
        title = elem.attrib.get("Title", "").strip()
        body = elem.attrib.get("Body", "").strip()
        post_id = elem.attrib.get("Id", "")
        tags = elem.attrib.get("Tags", "")
        score = int(elem.attrib.get("Score", "0"))

        # Skip very low quality posts
        if not title or not body or score < 1:
            elem.clear()
            continue

        # Build clean content: title + tags header + HTML body
        content = f"# {title}\n\nTags: {tags}\n\n{body}"
        yield post_id, title, content
        elem.clear()

# ─── API client ───────────────────────────────────────────────────────────────

class DevPulseClient:
    def __init__(self, base_url: str, token: str, workspace_id: str):
        self.base = base_url.rstrip("/")
        self.workspace_id = workspace_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def import_document(self, title: str, content: str) -> dict:
        """POST /api/workspaces/{id}/documents/import-so with SO HTML content."""
        resp = self.session.post(
            f"{self.base}/api/workspaces/{self.workspace_id}/documents/import-so",
            json={"url": f"inline://{title}", "content": content},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if not Path(args.input).exists():
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    client = DevPulseClient(args.api_url, args.token, args.workspace_id)
    imported_ids = load_progress(args.progress_file) if args.resume else set()

    print(f"Starting import (limit={args.limit:,}, resume={args.resume})")
    print(f"Already imported: {len(imported_ids):,} posts")
    print()

    count = 0
    errors = 0
    start_time = time.time()

    for post_id, title, content in parse_posts(args.input):
        if count >= args.limit:
            break

        if args.resume and post_id in imported_ids:
            continue

        try:
            client.import_document(title, content)
            imported_ids.add(post_id)
            count += 1

            if count % 100 == 0:
                elapsed = time.time() - start_time
                rate = count / elapsed
                remaining = (args.limit - count) / rate if rate > 0 else 0
                print(
                    f"  Imported {count:,}/{args.limit:,} | "
                    f"{rate:.1f} docs/s | "
                    f"ETA {remaining/60:.1f}m | "
                    f"errors: {errors}"
                )
                save_progress(args.progress_file, imported_ids)

        except requests.HTTPError as e:
            errors += 1
            print(f"  WARN: post {post_id} failed ({e.response.status_code}) — skipping")
            if errors > 50:
                print("ERROR: Too many consecutive errors, stopping.", file=sys.stderr)
                save_progress(args.progress_file, imported_ids)
                sys.exit(1)
        except Exception as e:
            errors += 1
            print(f"  WARN: post {post_id} error: {e} — skipping")

        time.sleep(args.batch_delay)

    save_progress(args.progress_file, imported_ids)
    elapsed = time.time() - start_time
    print()
    print(f"Done: {count:,} documents imported in {elapsed:.1f}s ({errors} errors)")
    print(f"Progress saved to {args.progress_file}")


if __name__ == "__main__":
    main()
