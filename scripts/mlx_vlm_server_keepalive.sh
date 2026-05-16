#!/usr/bin/env bash
# Keep-alive wrapper for mlx_vlm.server (the VISION model server).
#
# Why this exists: qwen_vl_local used to load Qwen 2.5 VL *inside each
# per-episode hermes subprocess*. That loaded a ~3 GB model fresh every
# episode, churning multi-GB allocations through Apple Silicon's shared
# GPU memory until the Mac hung. Running the VL model as ONE persistent
# server (loaded once) and making qwen_vl_local a thin HTTP client fixes
# that — exactly how the reasoning model already runs via
# mlx_server_keepalive.sh on :8080.
#
# Start:
#   nohup ~/tron1-sim-mac/mlx_vlm_server_keepalive.sh > /tmp/mlx-vlm-keepalive.log 2>&1 &
#   disown
#
# Stop:
#   kill $(cat /tmp/mlx-vlm-keepalive.pid)

set -u

VENV="/Users/justinsuo/.hermes/hermes-agent/venv"
MODEL="${MLX_VLM_MODEL:-mlx-community/Qwen2.5-VL-3B-Instruct-4bit}"
PORT="${MLX_VLM_PORT:-8081}"
LOG="${MLX_VLM_LOG:-/tmp/mlx-vlm.log}"
PID_FILE="/tmp/mlx-vlm-keepalive.pid"

echo $$ > "$PID_FILE"

cleanup() {
  echo "[vlm-keepalive] terminating"
  pkill -P $$ 2>/dev/null
  rm -f "$PID_FILE"
  exit 0
}
trap cleanup INT TERM EXIT

tries=0
while true; do
  tries=$((tries+1))
  echo "[vlm-keepalive $(date '+%H:%M:%S')] starting mlx_vlm.server ($MODEL on :$PORT) — attempt #$tries"
  # Routed through mlx_capped.py — the VL model's image inference is the
  # biggest Metal-buffer balloon, so it gets a larger budget than the
  # reasoning model but still a hard ceiling. --prefill-step-size 256
  # keeps peak prefill memory low.
  MLX_MEM_LIMIT_GB="${MLX_MEM_LIMIT_GB:-12}" \
  MLX_CACHE_LIMIT_GB="${MLX_CACHE_LIMIT_GB:-0.5}" \
  MLX_WIRED_LIMIT_GB="${MLX_WIRED_LIMIT_GB:-12}" \
  "$VENV/bin/python" /Users/justinsuo/tron1-sim-mac/mlx_capped.py mlx_vlm.server \
      --model "$MODEL" \
      --host 127.0.0.1 --port "$PORT" \
      --prefill-step-size 256 \
      >> "$LOG" 2>&1 &
  SERVER_PID=$!
  wait $SERVER_PID
  rc=$?
  echo "[vlm-keepalive $(date '+%H:%M:%S')] mlx_vlm.server exited with rc=$rc — restarting in 3s"
  sleep 3
done
