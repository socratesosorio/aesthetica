#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash tests/web_detection/run_visual_seed30.sh [limit_images] [top_k_max] [initial_top_k]
#
# Example:
#   bash tests/web_detection/run_visual_seed30.sh 3 8 5

LIMIT_IMAGES="${1:-3}"
TOP_K_MAX="${2:-8}"
INITIAL_TOP_K="${3:-5}"

export PYTHONPATH="${PYTHONPATH:-services/ml}"
export OPENAI_MIN_INTERVAL_SEC="${OPENAI_MIN_INTERVAL_SEC:-6}"
export OPENAI_MAX_RETRIES="${OPENAI_MAX_RETRIES:-8}"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Missing OPENAI_API_KEY. Export it, then rerun."
  exit 1
fi
if [[ -z "${SERPAPI_API_KEY:-}" ]]; then
  echo "Missing SERPAPI_API_KEY. Export it, then rerun."
  exit 1
fi

OUT="tests/web_detection/_reports/catalog_dataset_report_seed30.html"

./.venv/bin/python tests/web_detection/run_catalog_visual_dataset.py \
  --dir "tests/web_detection/test_images/seed30" \
  --limit-images "${LIMIT_IMAGES}" \
  --top-k-max "${TOP_K_MAX}" \
  --initial-top-k "${INITIAL_TOP_K}" \
  --sleep-between-images 3 \
  --rich-context \
  --out "${OUT}"

open "${OUT}"
