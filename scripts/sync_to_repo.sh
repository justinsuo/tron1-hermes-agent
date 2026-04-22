#!/usr/bin/env bash
# Refresh the repo's status/, skills/, and hermes_tools/ directories from the
# live working copies on disk. Called by auto_push.sh on a schedule.
#
# Invariant: this script only COPIES files — never deletes the repo tree,
# never touches .git, never touches secrets.

set -euo pipefail

REPO="/Users/justinsuo/tron1-hermes-agent"
STATUS="${REPO}/status"
mkdir -p "${STATUS}/transcripts" "${STATUS}/skills"

# --- 1. Code (in case you edited the live copy since last sync) ---
cp -f /Users/justinsuo/tron1-sim-mac/sim.py                 "${REPO}/sim/"                 2>/dev/null || true
cp -f /Users/justinsuo/tron1-sim-mac/gauge_render.py        "${REPO}/sim/"                 2>/dev/null || true
cp -f /Users/justinsuo/tron1-sim-mac/record_demo.py         "${REPO}/sim/"                 2>/dev/null || true
cp -f /Users/justinsuo/tron1-sim-mac/demo.py                "${REPO}/sim/"                 2>/dev/null || true
cp -f /Users/justinsuo/tron1-sim-mac/assets/scene.xml       "${REPO}/sim/assets/"          2>/dev/null || true
cp -f /Users/justinsuo/tron1-sim-mac/dashboard_server.py    "${REPO}/dashboard/"           2>/dev/null || true
cp -f /Users/justinsuo/tron1-sim-mac/DELIVERY.md            "${REPO}/"                     2>/dev/null || true
cp -f /Users/justinsuo/tron1-sim-mac/start_all.sh           "${REPO}/scripts/"             2>/dev/null || true
cp -f /Users/justinsuo/tron1-selfplay/tasks.py              "${REPO}/selfplay/"            2>/dev/null || true
cp -f /Users/justinsuo/tron1-selfplay/robotics_selfplay.py  "${REPO}/selfplay/"            2>/dev/null || true
cp -f /Users/justinsuo/tron1-selfplay/robotics_log.py       "${REPO}/selfplay/"            2>/dev/null || true
cp -f /Users/justinsuo/.hermes/hermes-agent/tools/tron1_ros2_tool.py   "${REPO}/hermes_tools/" 2>/dev/null || true
cp -f /Users/justinsuo/.hermes/hermes-agent/tools/qwen_vl_local_tool.py "${REPO}/hermes_tools/" 2>/dev/null || true

# --- 2. Skill files (the agent edits these during self-play) ---
for sk in read-wall-gauge navigate-to-landmark avoid-obstacle describe-scene; do
  src="/Users/justinsuo/.hermes/skills/robotics/${sk}/SKILL.md"
  [[ -f "$src" ]] && cp -f "$src" "${REPO}/skills/${sk}.md"
  [[ -f "$src" ]] && cp -f "$src" "${STATUS}/skills/${sk}.md"
done

# --- 3. Episode log — copy and tail (full log stays local; repo gets recent 500) ---
LOG="/Users/justinsuo/.tron1-robotics-log.jsonl"
if [[ -f "$LOG" ]]; then
  tail -n 500 "$LOG" > "${STATUS}/episodes_recent.jsonl"
fi

# --- 4. Recent transcripts (last 10) ---
TRANSCRIPTS="/Users/justinsuo/.tron1-transcripts"
if [[ -d "$TRANSCRIPTS" ]]; then
  rm -f "${STATUS}/transcripts/"*.txt 2>/dev/null || true
  ls -t "$TRANSCRIPTS"/*.txt 2>/dev/null | head -10 | while read -r f; do
    cp -f "$f" "${STATUS}/transcripts/"
  done
fi

# --- 5. Fresh dashboard screenshots (top / ego / chase cameras) ---
python3 - <<'PY' 2>/dev/null || true
import json, socket, base64, os
from pathlib import Path
out = Path("/Users/justinsuo/tron1-hermes-agent/status")
out.mkdir(exist_ok=True)
def call(op, **kw):
    try:
        with socket.create_connection(("127.0.0.1", 5556), timeout=3) as s:
            s.settimeout(5)
            s.sendall((json.dumps({"op": op, **kw}) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                c = s.recv(65536); buf += c
                if not c: break
            return json.loads(buf) if buf else {}
    except Exception:
        return {}
for cam in ("top", "ego", "tp"):
    r = call("get_image", camera=cam)
    if r.get("ok"):
        (out / f"cam_{cam}.jpg").write_bytes(base64.b64decode(r["data"]["jpeg_base64"]))
# Snapshot gauge truths + pose for README
gauges = call("all_gauges_truth").get("data", {})
pose = call("get_pose").get("data", {})
(out / "live.json").write_text(json.dumps({"gauges": gauges, "pose": pose}, indent=2))
PY

# --- 6. Update status/stats.md with per-task metrics ---
python3 - <<'PY'
import json, time
from pathlib import Path
from collections import defaultdict

status = Path("/Users/justinsuo/tron1-hermes-agent/status")
log = Path.home() / ".tron1-robotics-log.jsonl"
if not log.exists():
    (status / "stats.md").write_text("# Stats\n\nNo episodes yet.\n")
    raise SystemExit(0)

per_task = defaultdict(lambda: {"total": 0, "ok": 0, "r_sum": 0.0})
total = 0
recent = []
for line in log.read_text().splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        continue
    if e.get("event") != "episode_end":
        continue
    total += 1
    t = e.get("task", "?")
    s = per_task[t]
    s["total"] += 1
    if e.get("success"): s["ok"] += 1
    s["r_sum"] += float(e.get("reward", 0.0))
    recent.append(e)

last30 = recent[-30:]
recent_rate = sum(1 for e in last30 if e.get("success")) / max(1, len(last30)) * 100

lines = []
lines.append(f"# Live Progress\n")
lines.append(f"**Last updated**: {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
lines.append(f"**Total episodes**: {total}  \n")
lines.append(f"**Success rate (last 30)**: {recent_rate:.0f}%\n")
lines.append("\n## Per-task\n")
lines.append("| task | passes / total | success % | avg reward |")
lines.append("|---|---|---|---|")
for task, s in sorted(per_task.items(), key=lambda kv: kv[1]["ok"]/max(1,kv[1]["total"]), reverse=True):
    rate = s["ok"] / max(1, s["total"]) * 100
    avg = s["r_sum"] / max(1, s["total"])
    lines.append(f"| `{task}` | {s['ok']}/{s['total']} | {rate:.0f}% | {avg:+.2f} |")

lines.append("\n## Last 15 episodes\n")
lines.append("| # | task | result | reward | reason |")
lines.append("|---|---|---|---|---|")
for i, e in enumerate(reversed(recent[-15:])):
    mark = "✓" if e.get("success") else "✗"
    lines.append(f"| {total - i} | `{e.get('task','?')}` | {mark} | {e.get('reward',0):+.2f} | {e.get('reason','')[:60]} |")

(status / "stats.md").write_text("\n".join(lines) + "\n")

# Also drop a machine-readable version for the README generator
(status / "stats.json").write_text(json.dumps({
    "total": total,
    "recent_rate_pct": round(recent_rate, 1),
    "per_task": {k: {"ok": v["ok"], "total": v["total"],
                      "rate_pct": round(v["ok"]/max(1,v["total"])*100, 1),
                      "avg_reward": round(v["r_sum"]/max(1,v["total"]), 3)}
                  for k, v in per_task.items()},
    "ts": time.time(),
}, indent=2))
PY

# --- 7. Regenerate the top-level README.md with embedded stats ---
python3 /Users/justinsuo/tron1-hermes-agent/scripts/render_readme.py || true

touch "${STATUS}/updated_at.txt"
date '+%Y-%m-%d %H:%M:%S' > "${STATUS}/updated_at.txt"

echo "[sync] done $(date '+%H:%M:%S')"
