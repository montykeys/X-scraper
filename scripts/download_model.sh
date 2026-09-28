#!/usr/bin/env bash
# Downloads the local sub-1B model used by x_scraper.local_model.
# Qwen2.5-0.5B-Instruct, Q4_K_M quantization (~350MB), CPU-friendly.
set -euo pipefail

MODEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/models"
mkdir -p "$MODEL_DIR"

URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
OUT="$MODEL_DIR/qwen2.5-0.5b-instruct-q4_k_m.gguf"

if [ -f "$OUT" ]; then
  echo "Model already present at $OUT"
  exit 0
fi

echo "Downloading $URL -> $OUT"
curl -L --fail -o "$OUT" "$URL"
echo "Done. Set X_SCRAPER_MODEL_PATH=$OUT if not using the default location."
