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
  "$VENV/bin/python" -m mlx_lm server \
      --model "$MODEL" \
      --host 127.0.0.1 --port "$PORT" \
      --log-level INFO \
      >> "$LOG" 2>&1 &
  SERVER_PID=$!
  wait $SERVER_PID
  rc=$?
  echo "[keepalive $(date '+%H:%M:%S')] mlx_lm.server exited with rc=$rc — restarting in 3s"
  sleep 3
done
