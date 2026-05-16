#!/usr/bin/env bash
# Memory guardian — the safety net that keeps overnight self-play from
# ever hanging the Mac.
#
# Background: after extensive bisection (2026-05-15), every component of
# the stack proved stable in isolation — sim, renderer, the mlx_lm
# reasoning server, the mlx_vlm vision server. The instability is a
# diffuse, multi-process memory balloon that only appears during heavy
# multi-turn self-play episodes (agent driving VL + LM + renderer
# concurrently). Rather than chase a single smoking gun that may not
# exist, this guardian makes the workload fail safely instead of the
# machine.
#
# Behaviour: samples free memory every 3s.
#   - free < DANGER : kill ONLY the current episode's `hermes chat`
#     subprocess. self-play (robotics_selfplay.py) keeps running — its
#     subprocess.run() returns non-zero, the episode is logged as a
#     failure, and the next episode starts after the normal delay. The
#     machine never reaches the hang threshold.
#   - free < WARN   : log a warning line.
#
# It deliberately does NOT kill robotics_selfplay.py itself, the mlx
# servers, the sim, or the hermes gateway — only the runaway episode.
#
# Logs to ~/tron1-bisect.log (survives reboot).

# Thresholds raised + sampling tightened after the 2026-05-15 P5 run,
# where the balloon dropped free memory ~88%->5% in under 9s. Culling at
# 26% left only a thin margin. At 42% the guardian fires ~20 GB sooner,
# while the balloon is still climbing — comfortably before any hang.
LOG="${TRON1_MEMGUARD_LOG:-$HOME/tron1-bisect.log}"
DANGER="${TRON1_MEM_DANGER:-42}"   # cull the episode below this free%
WARN="${TRON1_MEM_WARN:-55}"       # log a warning below this
POLL="${TRON1_MEM_POLL:-2}"        # seconds between samples
echo "=== memguard start $(date) danger<${DANGER}% warn<${WARN}% poll=${POLL}s ===" >> "$LOG"

while true; do
  free_raw=$(memory_pressure 2>/dev/null | grep -oE '[0-9]+%' | head -1)
  free=${free_raw%\%}
  ts=$(date '+%H:%M:%S')
  if [ -z "$free" ]; then
    sleep "$POLL"; continue
  fi
  if [ "$free" -lt "$DANGER" ]; then
    # Kill only the episode subprocess (hermes chat ...). Leaves
    # self-play, the gateway, the mlx servers and the sim alone.
    if pgrep -f "hermes chat" > /dev/null 2>&1; then
      echo "[$ts] guardian: free=${free}% < ${DANGER}% — culling current episode (hermes chat)" >> "$LOG"
      pkill -9 -f "hermes chat" 2>/dev/null
      sleep 6
      free2=$(memory_pressure 2>/dev/null | grep -oE '[0-9]+%' | head -1)
      echo "[$ts] guardian: episode culled, free now ${free2}" >> "$LOG"
    else
      # No episode to cull but still low — log it; self-play delay will
      # let memory settle on its own.
      echo "[$ts] guardian: free=${free}% low but no episode running" >> "$LOG"
      sleep 5
    fi
  elif [ "$free" -lt "$WARN" ]; then
    echo "[$ts] guardian: WARN free=${free}%" >> "$LOG"
  fi
  sleep "$POLL"
done
