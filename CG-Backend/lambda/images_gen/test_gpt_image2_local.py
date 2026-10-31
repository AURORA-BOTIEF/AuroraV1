#!/usr/bin/env python3
"""
Local smoke test for OpenAI Images API using the same contract as ImagesGen (no response_format).

Usage:
  export OPENAI_API_KEY='sk-...'
  python test_gpt_image2_local.py

Or load key from AWS Secrets Manager (profile Netec):
  export OPENAI_API_KEY="$(aws secretsmanager get-secret-value --profile Netec --region us-east-1 \
    --secret-id aurora/openai-api-key --query SecretString --output text | python3 -c \"import sys,json; print(json.load(sys.stdin).get('api_key',''))\")"
  python test_gpt_image2_local.py

Writes: ./gpt-image-2-test-output.png (or path from OUTPUT_PATH).
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request

OPENAI_IMAGES_GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
DEFAULT_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print(
            "Missing OPENAI_API_KEY. Load from env or from Secrets Manager (see docstring).",
            file=sys.stderr,
        )
        return 1

    prompt = os.environ.get(
        "TEST_IMAGE_PROMPT",
        "Simple educational diagram: three labeled boxes A, B, C connected by arrows, flat style, white background.",
    )
    size = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024")

    payload = {
        "model": DEFAULT_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_IMAGES_GENERATIONS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    print(f"POST {OPENAI_IMAGES_GENERATIONS_URL}")
    print(f"model={DEFAULT_MODEL!r} size={size!r} prompt_len={len(prompt)}")

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {err[:2000]}", file=sys.stderr)
        return 2

    data = json.loads(raw)
    items = data.get("data") or []
    if not items:
        print("Response missing data[]:", json.dumps(data)[:1500], file=sys.stderr)
        return 3

    out_path = os.environ.get("OUTPUT_PATH", "gpt-image-2-test-output.png")
    item0 = items[0]

    if item0.get("b64_json"):
        img_bytes = base64.b64decode(item0["b64_json"])
        print("Got b64_json in response.")
    elif item0.get("url"):
        url = item0["url"]
        print(f"Got url in response, downloading: {url[:80]}...")
        with urllib.request.urlopen(url, timeout=120) as url_resp:
            img_bytes = url_resp.read()
    else:
        print("No b64_json or url in data[0]:", json.dumps(item0)[:800], file=sys.stderr)
        return 4

    if len(img_bytes) < 100:
        print(f"Image too small: {len(img_bytes)} bytes", file=sys.stderr)
        return 5

    with open(out_path, "wb") as f:
        f.write(img_bytes)
    print(f"OK wrote {len(img_bytes)} bytes -> {os.path.abspath(out_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
