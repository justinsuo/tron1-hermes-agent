#!/usr/bin/env bash
# Keep-alive wrapper for mlx_lm.server.
#
# The server occasionally crashes on broken-pipe writes (client timeout +
# server mid-response). This wrapper respawns it immediately on exit and
# logs every crash + restart.
#
# Start:
#   nohup ~/tron1-sim-mac/mlx_server_keepalive.sh > /tmp/mlx-keepalive.log 2>&1 &
#   disown
#
# Stop:
#   kill $(cat /tmp/mlx-keepalive.pid)

set -u

VENV="/Users/justinsuo/.hermes/hermes-agent/venv"
MODEL="${MLX_MODEL:-mlx-community/Qwen3-14B-4bit}"
PORT="${MLX_PORT:-8080}"
LOG="${MLX_LOG:-/tmp/mlx-lm.log}"
PID_FILE="/tmp/mlx-keepalive.pid"

echo $$ > "$PID_FILE"

cleanup() {
  echo "[keepalive] terminating"
  pkill -P $$ 2>/dev/null
  rm -f "$PID_FILE"
  exit 0
}
trap cleanup INT TERM EXIT

tries=0
while true; do
  tries=$((tries+1))
  echo "[keepalive $(date '+%H:%M:%S')] starting mlx_lm.server ($MODEL on :$PORT) — attempt #$tries"
  # Flags:
  #   --chat-template-args '{"enable_thinking": false}'
  #     Qwen 3 defaults to <think>…</think> reasoning which Hermes strips →
  #     empty transcript. Disable it.
  #   --prompt-cache-size 8192
  #     Keep 8K tokens of KV cache across requests. Every self-play episode
  #     sends the same tool schemas + SKILL.md content as system prompt;
  #     reusing the cached prefix saves 1-3 seconds per episode.
  #   --prefill-step-size 1024
  #     Bigger prefill batches = faster first-token on long prompts (system
  #     prompt + skills can be 4-6K tokens).
  #   --prompt-concurrency 1 / --decode-concurrency 1
  #     Self-play is strictly serial (one hermes chat at a time), so keeping
  #     concurrency at 1 dodges MoE router overhead.
  # Routed through mlx_capped.py so MLX cannot wire enough Metal memory
  # to hang the Mac. Caps (GB) come from the env, with safe defaults for
  # the 4B reasoning model. prompt-cache-size cut 8192 -> 2048 to shrink
  # the KV cache footprint.
  MLX_MEM_LIMIT_GB="${MLX_MEM_LIMIT_GB:-7}" \
  MLX_CACHE_LIMIT_GB="${MLX_CACHE_LIMIT_GB:-0.5}" \
  MLX_WIRED_LIMIT_GB="${MLX_WIRED_LIMIT_GB:-7}" \
  "$VENV/bin/python" /Users/justinsuo/tron1-sim-mac/mlx_capped.py mlx_lm server \
      --model "$MODEL" \
      --host 127.0.0.1 --port "$PORT" \
      --chat-template-args '{"enable_thinking": false}' \
      --prompt-cache-size 2048 \
      --prefill-step-size 512 \
      --prompt-concurrency 1 \
      --decode-concurrency 1 \
      --log-level INFO \
      >> "$LOG" 2>&1 &
  SERVER_PID=$!
  wait $SERVER_PID
  rc=$?
  echo "[keepalive $(date '+%H:%M:%S')] mlx_lm.server exited with rc=$rc — restarting in 3s"
  sleep 3
done
