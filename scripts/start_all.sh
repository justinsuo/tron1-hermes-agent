#!/usr/bin/env bash
# One-command startup for the Tron 1 Hermes Agent deliverable.
# Brings up the sim (headless), the dashboard, and optionally self-play.
#
#   ./start_all.sh              # sim + dashboard (no self-play)
#   ./start_all.sh selfplay 10  # also run 10 self-play episodes
#   ./start_all.sh viewer       # open the MuJoCo viewer in Terminal.app

set -euo pipefail

VENV="/Users/justinsuo/.hermes/hermes-agent/venv"
SIM_DIR="/Users/justinsuo/tron1-sim-mac"
SELFPLAY_DIR="/Users/justinsuo/tron1-selfplay"

SIM_PORT=5556
DASH_PORT=5557
MODE="${1:-}"

# --- 0. stop anything already running ---
pkill -9 -f "tron1-sim-mac/sim.py" 2>/dev/null || true
pkill -9 -f "dashboard_server.py" 2>/dev/null || true
pkill -9 -f "robotics_selfplay.py" 2>/dev/null || true
sleep 1

# --- 1. start the sim ---
if [[ "$MODE" == "viewer" ]]; then
  echo "[start] launching MuJoCo viewer in Terminal.app"
  osascript -e 'tell application "Terminal" to activate' \
            -e "tell application \"Terminal\" to do script \"${VENV}/bin/mjpython ${SIM_DIR}/sim.py --viewer\"" \
            >/dev/null
else
  echo "[start] launching headless sim on port ${SIM_PORT}"
  nohup "${VENV}/bin/python" "${SIM_DIR}/sim.py" > /tmp/tron1-sim.log 2>&1 &
fi

# wait for TCP listener
for i in {1..15}; do
  if lsof -i :${SIM_PORT} | grep -q LISTEN 2>/dev/null; then
    echo "[start] sim up on :${SIM_PORT}"
    break
  fi
  sleep 0.5
done

# --- 2. start the dashboard ---
echo "[start] launching dashboard on port ${DASH_PORT}"
nohup "${VENV}/bin/python" "${SIM_DIR}/dashboard_server.py" --port ${DASH_PORT} \
  > /tmp/tron1-dashboard.log 2>&1 &
sleep 1
echo "[start] dashboard: http://127.0.0.1:${DASH_PORT}/"

# --- 3. optional self-play ---
if [[ "$MODE" == "selfplay" ]]; then
  ROUNDS="${2:-10}"
  echo "[start] running ${ROUNDS} self-play episodes (log: /tmp/tron1-selfplay.log)"
  nohup "${VENV}/bin/python" "${SELFPLAY_DIR}/robotics_selfplay.py" \
    --rounds "${ROUNDS}" --delay 2 \
    > /tmp/tron1-selfplay.log 2>&1 &
fi

echo ""
echo "status:"
printf "  sim       : "; lsof -i :${SIM_PORT} 2>/dev/null | grep -q LISTEN && echo "✓ listening" || echo "✗ not up"
printf "  dashboard : "; lsof -i :${DASH_PORT} 2>/dev/null | grep -q LISTEN && echo "✓ listening" || echo "✗ not up"
echo ""
echo "tail the logs:  tail -f /tmp/tron1-sim.log /tmp/tron1-dashboard.log /tmp/tron1-selfplay.log"
echo "open:           open http://127.0.0.1:${DASH_PORT}/"
