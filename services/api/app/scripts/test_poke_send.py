#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

import httpx
from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a quick test message to Poke.")
    parser.add_argument(
        "--message",
        default="Aesthetica test message",
        help="Message body to send.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional override for POKE_API_KEY.",
    )
    parser.add_argument(
        "--webhook-url",
        default=None,
        help="Optional override for POKE_WEBHOOK_URL.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    api_key = (args.api_key or os.getenv("POKE_API_KEY", "")).strip()
    webhook_url = (args.webhook_url or os.getenv("POKE_WEBHOOK_URL", "")).strip()

    if not api_key:
        print("error: missing POKE_API_KEY (set in .env or pass --api-key)", file=sys.stderr)
        return 2
    if not webhook_url:
        print("error: missing POKE_WEBHOOK_URL (set in .env or pass --webhook-url)", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"message": args.message}

    try:
        response = httpx.post(webhook_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text.strip()
        print(f"error: poke returned {exc.response.status_code}: {body}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - direct script failure path
        print(f"error: request failed: {exc}", file=sys.stderr)
        return 1

    print(f"ok: sent message ({response.status_code})")
    if response.text.strip():
        print(response.text.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
