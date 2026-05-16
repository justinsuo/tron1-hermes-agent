#!/usr/bin/env bash
# Fine-grained process monitor. Every 5s appends free% + top-8 RSS to
# ~/tron1-bisect.log so a crash leaves the culprit in the last lines.
LOG="$HOME/tron1-bisect.log"
DURATION="${1:-600}"
start=$(date +%s)
echo "=== procmon start $(date) ===" >> "$LOG"
while [ $(( $(date +%s) - start )) -lt "$DURATION" ]; do
  free=$(memory_pressure 2>/dev/null | grep -oE '[0-9]+%' | head -1 || echo "?")
  top=$(ps -A -o rss,comm | sort -rn | head -8 | awk '{printf "%.0fMB:%s ", $1/1024, substr($2,1,28)}')
  echo "[$(date '+%H:%M:%S')] free=$free | $top" >> "$LOG"
  sleep 5
done
echo "=== procmon end $(date) ===" >> "$LOG"
