#!/usr/bin/env bash
# 5-hour self-play supervisor.
#
# Keeps robotics_selfplay.py alive continuously for `DURATION_SEC` seconds.
# If a batch finishes, starts the next one. If the sim dies, attempts a
# restart. If the whole process is killed, cleans up child processes.
#
# Start:
#   nohup ~/tron1-selfplay/supervisor.sh > /tmp/tron1-supervisor.log 2>&1 &
#   disown
#
# Status:
#   tail -f /tmp/tron1-supervisor.log
#
# Stop early:
#   kill $(cat /tmp/tron1-supervisor.pid)

set -u

DURATION_SEC="${DURATION_SEC:-18000}"       # 5 hours default
BATCH_ROUNDS="${BATCH_ROUNDS:-50}"          # rounds per spawned batch
BATCH_DELAY="${BATCH_DELAY:-3}"             # seconds between episodes
VENV="/Users/justinsuo/.hermes/hermes-agent/venv"
SELFPLAY="/Users/justinsuo/tron1-selfplay/robotics_selfplay.py"
SIM_SCRIPT="/Users/justinsuo/tron1-sim-mac/sim.py"
LOG_FILE="${LOG_FILE:-/tmp/tron1-supervisor.log}"
PID_FILE="/tmp/tron1-supervisor.pid"

echo $$ > "$PID_FILE"
END_TS=$(( $(date +%s) + DURATION_SEC ))

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

cleanup() {
  log "supervisor stopping (PID $$)"
  pkill -f robotics_selfplay 2>/dev/null
  rm -f "$PID_FILE"
  exit 0
}
trap cleanup INT TERM EXIT

log "supervisor start · duration=${DURATION_SEC}s · batch=${BATCH_ROUNDS} rounds · delay=${BATCH_DELAY}s"
log "end time: $(date -r ${END_TS} '+%Y-%m-%d %H:%M:%S')"

batch=0
while [ "$(date +%s)" -lt "$END_TS" ]; do
  batch=$((batch+1))
  remaining=$(( END_TS - $(date +%s) ))

  # Ensure sim is up; if not, spawn headless sim
  if ! lsof -i :5556 2>/dev/null | grep -q LISTEN; then
    log "sim not responding — spawning headless sim"
    nohup "$VENV/bin/python" "$SIM_SCRIPT" > /tmp/tron1-sim.log 2>&1 &
    disown
    sleep 5
  fi

  # Don't overlap with an existing self-play that's still running
  if pgrep -f robotics_selfplay > /dev/null 2>&1; then
    log "self-play already running, waiting 30s"
    sleep 30
    continue
  fi

  # Cap the batch size so we don't overshoot the end time
  avg_per_ep=50           # rough 50s per episode on Haiku + ~2s delay
  max_rounds=$(( remaining / avg_per_ep ))
  use_rounds=$BATCH_ROUNDS
  if [ "$max_rounds" -lt "$use_rounds" ] && [ "$max_rounds" -gt 0 ]; then
    use_rounds=$max_rounds
  fi
  if [ "$use_rounds" -lt 1 ]; then
    log "only ${remaining}s left — not starting another batch"
    break
  fi

  log "batch #${batch}: spawning self-play with ${use_rounds} rounds (remaining=${remaining}s)"
  "$VENV/bin/python" "$SELFPLAY" --rounds "$use_rounds" --delay "$BATCH_DELAY" \
      >> "$LOG_FILE.selfplay" 2>&1
  rc=$?
  log "batch #${batch} finished with rc=$rc"

  sleep 5
done

log "supervisor done after $((batch)) batches"
cleanup
