#!/usr/bin/env bash
# Tron 1 · Hermes Agent — one-click launcher.
# Double-click this file on the Desktop to bring everything up and open the
# dashboard in your default browser.
#
# Safe to run repeatedly — if something's already up, it's left alone.

set -u

REPO="/Users/justinsuo/tron1-hermes-agent"
VENV="/Users/justinsuo/.hermes/hermes-agent/venv"
SIM="/Users/justinsuo/tron1-sim-mac/sim.py"
DASH="/Users/justinsuo/tron1-sim-mac/dashboard_server.py"

DASH_URL="http://127.0.0.1:5557/"

banner() {
  printf "\033[1;35m\n"
  printf "┌──────────────────────────────────────────────┐\n"
  printf "│     🤖  Tron 1 · Hermes Agent · Launcher     │\n"
  printf "└──────────────────────────────────────────────┘\033[0m\n\n"
}

up_on_port() { lsof -i :"$1" 2>/dev/null | grep -q LISTEN; }

start_sim() {
  if up_on_port 5556; then
    echo "  ✓ sim already running on :5556"
    return
  fi
  echo "  → starting sim (headless)…"
  nohup "$VENV/bin/python" "$SIM" > /tmp/tron1-sim.log 2>&1 &
  disown
  for _ in {1..15}; do
    up_on_port 5556 && { echo "  ✓ sim up on :5556"; return; }
    sleep 0.5
  done
  echo "  ✗ sim failed to listen — check /tmp/tron1-sim.log"
}

start_dashboard() {
  if up_on_port 5557; then
    echo "  ✓ dashboard already running on :5557"
    return
  fi
  echo "  → starting dashboard…"
  nohup "$VENV/bin/python" "$DASH" --port 5557 > /tmp/tron1-dashboard.log 2>&1 &
  disown
  for _ in {1..15}; do
    up_on_port 5557 && { echo "  ✓ dashboard up on :5557"; return; }
    sleep 0.5
  done
  echo "  ✗ dashboard failed to listen — check /tmp/tron1-dashboard.log"
}

autopush_check() {
  if launchctl list 2>/dev/null | grep -q com.justinsuo.tron1-autopush; then
    echo "  ✓ auto-push to GitHub is scheduled"
  else
    echo "  → loading auto-push schedule…"
    launchctl load "$HOME/Library/LaunchAgents/com.justinsuo.tron1-autopush.plist" 2>/dev/null \
      && echo "  ✓ auto-push scheduled" \
      || echo "  ✗ auto-push plist missing — skip"
  fi
}

open_dashboard() {
  echo ""
  echo "Opening dashboard: $DASH_URL"
  open "$DASH_URL"
}

menu() {
  cat <<EOF

What next?

  1) open the MuJoCo 3D viewer window (live 60 fps)
  2) run 10 self-play episodes (Haiku — cheap)
  3) run 30 self-play episodes
  4) force a GitHub sync right now
  5) stop self-play
  6) tail the self-play log
  q) quit (services keep running)

EOF
  read -p "choose: " ch
  case "$ch" in
    1) osascript -e 'tell application "Terminal" to activate' \
                 -e "tell application \"Terminal\" to do script \"$VENV/bin/mjpython $SIM --viewer\"" >/dev/null
       echo "viewer launching in Terminal.app" ;;
    2) curl -s -X POST -H "Content-Type: application/json" -d '{"rounds":10}' \
            "http://127.0.0.1:5557/api/control/selfplay/start" ; echo ;;
    3) curl -s -X POST -H "Content-Type: application/json" -d '{"rounds":30}' \
            "http://127.0.0.1:5557/api/control/selfplay/start" ; echo ;;
    4) bash "$REPO/scripts/auto_push.sh" | tail -5 ;;
    5) curl -s -X POST "http://127.0.0.1:5557/api/control/selfplay/stop" ; echo ;;
    6) tail -n 40 /tmp/tron1-selfplay*.log 2>/dev/null | tail -40 ;;
    q|Q) return ;;
    *) echo "unknown choice" ;;
  esac
  menu
}

# ------- main -------
cd "$HOME"
banner
echo "Bringing up services..."
start_sim
start_dashboard
autopush_check
open_dashboard
menu

echo ""
echo "Services left running in the background. Close this window when done."
echo "The dashboard stays at: $DASH_URL"
