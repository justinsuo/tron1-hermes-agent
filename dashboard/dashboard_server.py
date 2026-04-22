"""Browser-viewable progress dashboard for the Tron 1 Hermes agent.

Run alongside sim.py. Serves http://127.0.0.1:5557 showing:

  - Live top-down + ego camera feeds (refreshed every second)
  - Current robot pose, active command, gauge truths
  - Episode history from ~/.tron1-robotics-log.jsonl with pass/fail, reward,
    and a link to each transcript
  - Per-task success rate + reward trend
  - The robotics skill files with the "last edited" time (self-learning proof)

Start:
    ~/.hermes/hermes-agent/venv/bin/python \\
        ~/tron1-sim-mac/dashboard_server.py --port 5557
"""

from __future__ import annotations

import argparse
import base64
import html
import http.server
import io
import json
import logging
import os
import shlex
import socket
import socketserver
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any

SIM_HOST = os.getenv("HERMES_ROS2_HOST", "127.0.0.1")
SIM_PORT = int(os.getenv("HERMES_ROS2_PORT", "5556"))
LOG_PATH = Path.home() / ".tron1-robotics-log.jsonl"
TRANSCRIPT_DIR = Path.home() / ".tron1-transcripts"
SKILLS_DIR = Path.home() / ".hermes" / "skills" / "robotics"
REPO = Path.home() / "tron1-hermes-agent"
VENV = Path.home() / ".hermes" / "hermes-agent" / "venv"
SIM_SCRIPT = Path.home() / "tron1-sim-mac" / "sim.py"
SELFPLAY_SCRIPT = Path.home() / "tron1-selfplay" / "robotics_selfplay.py"

logger = logging.getLogger("dashboard")


# ---------------------------------------------------------------------------
# Sim client
# ---------------------------------------------------------------------------

def sim_call(op: str, timeout: float = 5.0, **fields: Any) -> dict:
    try:
        with socket.create_connection((SIM_HOST, SIM_PORT), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall((json.dumps({"op": op, **fields}) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk: break
                buf += chunk
            return json.loads(buf.decode()) if buf else {"ok": False}
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Log + skill readers
# ---------------------------------------------------------------------------

def read_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    out = []
    for line in LOG_PATH.read_text().splitlines():
        line = line.strip()
        if not line: continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def _find_pids(pattern: str) -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True)
        return [int(p) for p in out.strip().splitlines() if p.strip().isdigit()]
    except subprocess.CalledProcessError:
        return []


def component_status() -> dict:
    """Report live/dead state for each controllable component."""
    sim = _find_pids("tron1-sim-mac/sim.py")
    viewer = _find_pids("mjpython")
    dash = _find_pids("dashboard_server.py")
    selfp = _find_pids("robotics_selfplay.py")
    return {
        "sim":        {"up": _port_open(SIM_PORT), "pids": sim + viewer},
        "dashboard":  {"up": _port_open(5557),     "pids": dash},
        "selfplay":   {"up": len(selfp) > 0,       "pids": selfp},
        "autopush":   {"up": _autopush_loaded(),   "pids": []},
        "hermes_gw":  {"up": _launchctl_loaded("ai.hermes.gateway"), "pids": []},
    }


def _autopush_loaded() -> bool:
    return _launchctl_loaded("com.justinsuo.tron1-autopush")


def _launchctl_loaded(label: str) -> bool:
    try:
        out = subprocess.check_output(["launchctl", "list"], text=True)
        return any(line.split("\t")[-1].strip() == label for line in out.splitlines()[1:])
    except subprocess.CalledProcessError:
        return False


def _spawn(cmd: list[str], log_name: str) -> int:
    """Start a command fully detached; return PID. Output to /tmp/<log_name>."""
    log = open(f"/tmp/{log_name}", "ab", buffering=0)
    p = subprocess.Popen(
        cmd, stdout=log, stderr=log,
        start_new_session=True,
    )
    return p.pid


def do_action(component: str, action: str, rounds: int = 10) -> dict:
    """Central dispatcher. Returns {ok, msg, pids?}."""
    if component == "sim":
        if action == "start":
            if _port_open(SIM_PORT):
                return {"ok": True, "msg": "sim already running"}
            pid = _spawn(
                [str(VENV / "bin" / "python"), str(SIM_SCRIPT)],
                "tron1-sim.log",
            )
            return {"ok": True, "msg": f"sim started (PID {pid})", "pid": pid}
        if action == "stop":
            subprocess.run(["pkill", "-9", "-f", "tron1-sim-mac/sim.py"])
            subprocess.run(["pkill", "-9", "mjpython"])
            return {"ok": True, "msg": "sim stopped"}
        if action == "restart":
            subprocess.run(["pkill", "-9", "-f", "tron1-sim-mac/sim.py"])
            subprocess.run(["pkill", "-9", "mjpython"])
            time.sleep(1)
            pid = _spawn(
                [str(VENV / "bin" / "python"), str(SIM_SCRIPT)],
                "tron1-sim.log",
            )
            return {"ok": True, "msg": f"sim restarted (PID {pid})"}

    if component == "viewer":
        if action == "start":
            # mjpython --viewer needs to be the main thread; launch in Terminal.app
            script = f'{VENV}/bin/mjpython {SIM_SCRIPT} --viewer'
            subprocess.run(["pkill", "-9", "-f", "tron1-sim-mac/sim.py"])
            subprocess.run(["pkill", "-9", "mjpython"])
            time.sleep(1)
            subprocess.run([
                "osascript",
                "-e", 'tell application "Terminal" to activate',
                "-e", f'tell application "Terminal" to do script "{script}"',
            ])
            return {"ok": True, "msg": "viewer launching in Terminal.app"}

    if component == "selfplay":
        if action == "start":
            if _find_pids("robotics_selfplay.py"):
                return {"ok": True, "msg": "self-play already running"}
            pid = _spawn(
                [str(VENV / "bin" / "python"), str(SELFPLAY_SCRIPT),
                 "--rounds", str(rounds), "--delay", "2"],
                "tron1-selfplay.log",
            )
            return {"ok": True, "msg": f"self-play started ({rounds} rounds, PID {pid})", "pid": pid}
        if action == "stop":
            subprocess.run(["pkill", "-f", "robotics_selfplay"])
            return {"ok": True, "msg": "self-play stopped"}

    if component == "autopush":
        if action == "run":
            p = subprocess.Popen(
                ["bash", str(REPO / "scripts" / "auto_push.sh")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return {"ok": True, "msg": f"autopush kicked (PID {p.pid})"}
        if action == "start":
            subprocess.run([
                "launchctl", "load",
                str(Path.home() / "Library/LaunchAgents/com.justinsuo.tron1-autopush.plist"),
            ])
            return {"ok": True, "msg": "autopush schedule loaded"}
        if action == "stop":
            subprocess.run([
                "launchctl", "unload",
                str(Path.home() / "Library/LaunchAgents/com.justinsuo.tron1-autopush.plist"),
            ])
            return {"ok": True, "msg": "autopush schedule unloaded"}

    if component == "sim" and action == "reset":
        # Soft reset via sim TCP (no process kill)
        sim_call("reset")
        return {"ok": True, "msg": "robot reset to start pose"}

    return {"ok": False, "msg": f"unknown action {component}/{action}"}


def read_skills() -> list[dict]:
    rows = []
    if not SKILLS_DIR.exists():
        return rows
    for sk in sorted(SKILLS_DIR.iterdir()):
        sf = sk / "SKILL.md"
        if not sf.exists(): continue
        rows.append({
            "name": sk.name,
            "path": str(sf),
            "mtime": sf.stat().st_mtime,
            "size": sf.stat().st_size,
            "body": sf.read_text(),
        })
    return sorted(rows, key=lambda r: r["mtime"], reverse=True)


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Tron 1 Hermes Agent — Progress Dashboard</title>
<style>
  :root {
    --bg: #0f1115; --panel: #151924; --panel2: #1b2030;
    --txt: #e5e7ef; --dim: #848a9a; --accent: #7eb7ff;
    --ok: #5dd39e; --fail: #ff6b81;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
         background: var(--bg); color: var(--txt); }
  header { padding: 14px 20px; background: var(--panel); border-bottom: 1px solid #222;
           display: flex; align-items: center; justify-content: space-between; gap: 18px; }
  header h1 { margin: 0; font-size: 16px; font-weight: 600; }
  header .meta { font-size: 12px; color: var(--dim); }
  header .summary { font-size: 13px; color: var(--txt); display:flex; gap:12px; align-items:center; }
  header .summary .big { font-size: 22px; font-weight: 700; color: var(--ok); }
  header .summary .big.low { color: var(--fail); }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px; }
  @media (max-width: 1100px) { .grid { grid-template-columns: 1fr; } }
  .panel { background: var(--panel); border-radius: 8px; padding: 14px;
           border: 1px solid #242837; }
  .panel h2 { margin: 0 0 10px; font-size: 13px; font-weight: 600;
              text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent); }
  .cam-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .cam img { width: 100%; height: auto; border-radius: 4px; background: #000; }
  .cam .label { font-size: 11px; color: var(--dim); padding-top: 4px; }
  .kvs { display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px; font-size: 13px; }
  .kvs .k { color: var(--dim); }
  .kvs .v { font-family: ui-monospace, monospace; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { padding: 6px 8px; text-align: left; border-bottom: 1px solid #242837; }
  th { color: var(--dim); font-weight: 500; font-size: 11px; text-transform: uppercase; }
  .ok { color: var(--ok); } .fail { color: var(--fail); }
  .reward { font-family: ui-monospace, monospace; }
  .skill { margin-bottom: 14px; padding: 10px; background: var(--panel2); border-radius: 6px; position: relative; }
  .skill.fresh { border: 1px solid var(--ok); box-shadow: 0 0 8px rgba(93, 211, 158, 0.35); }
  .skill.fresh::before { content: "just edited"; position: absolute; right: 10px; top: 8px; font-size: 10px; color: var(--ok); background: #1f4531; padding: 2px 6px; border-radius: 10px; }
  .skill h3 { margin: 0 0 4px; font-size: 13px; }
  .skill .when { font-size: 11px; color: var(--dim); }
  .skill pre { margin: 6px 0 0; max-height: 220px; overflow: auto;
               background: #0b0d14; padding: 8px; border-radius: 4px;
               font-size: 11px; line-height: 1.4; white-space: pre-wrap; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 10px;
          font-size: 11px; background: #2c3247; margin-right: 4px; }
  @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
  .pill.ok { background: #1f4531; color: var(--ok); }
  .pill.fail { background: #4d2130; color: var(--fail); }
  .controls-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
  .ctrl { padding: 10px; background: var(--panel2); border-radius: 6px; }
  .ctrl .title { font-weight: 600; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
  .ctrl .sub { font-size: 11px; color: var(--dim); margin-top: 2px; margin-bottom: 8px; }
  .ctrl button { background: #2c3247; color: var(--txt); border: 0; padding: 5px 10px; margin-right: 5px; border-radius: 4px; font-size: 11px; cursor: pointer; font-family: inherit; }
  .ctrl button:hover { background: #3a435e; }
  .ctrl button.primary { background: #2e5e43; color: var(--ok); }
  .ctrl button.danger  { background: #5a2a36; color: var(--fail); }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
  .dot.up { background: var(--ok); box-shadow: 0 0 6px rgba(93, 211, 158, 0.6); }
  .dot.down { background: var(--fail); }
  .toast { margin-top: 8px; font-size: 12px; color: var(--dim); min-height: 18px; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<header>
  <h1>🤖 Tron 1 · Hermes Agent · Progress Dashboard</h1>
  <div class="summary" id="summary"></div>
  <div class="meta" id="meta">loading…</div>
</header>
<div class="grid">

  <div class="panel" style="grid-column: 1 / -1">
    <h2>Control Panel</h2>
    <div id="controls" class="controls-grid"></div>
    <div id="toast" class="toast"></div>
  </div>

  <div class="panel">
    <h2>Live sim</h2>
    <div class="cam-row">
      <div class="cam"><img id="cam-top" /><div class="label">top-down</div></div>
      <div class="cam"><img id="cam-ego" /><div class="label">robot ego</div></div>
    </div>
    <div class="cam" style="margin-top:10px"><img id="cam-tp" /><div class="label">chase</div></div>
    <div style="margin-top:12px"><b>Pose</b></div>
    <div class="kvs" id="pose-kvs"></div>
    <div style="margin-top:10px"><b>Gauges (ground truth)</b></div>
    <div class="kvs" id="gauge-kvs"></div>
  </div>

  <div class="panel">
    <h2>Episode log (latest 30)</h2>
    <div class="kvs" id="stats-kvs"></div>
    <div style="margin-top:8px"></div>
    <table id="ep-table">
      <thead><tr>
        <th>#</th><th>task</th><th>result</th><th>reward</th>
        <th>dur</th><th>when</th><th>why</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="panel" style="grid-column: 1 / -1">
    <h2>Skills (procedural memory)</h2>
    <div id="skills"></div>
  </div>
</div>

<script>
async function tick() {
  try {
    const j = await (await fetch('/api/state')).json();
    document.getElementById('meta').textContent =
      `sim ${j.sim_ok ? '✓' : '✗'}  ·  last update ${new Date().toLocaleTimeString()}`;

    // Running success rate summary
    const eps = j.episodes || [];
    const total = j.episode_count || 0;
    const passes = eps.filter(e => e.success).length;
    const recent = eps.length;
    const rate = recent ? (passes / recent * 100).toFixed(0) : 0;
    const rateCls = rate >= 70 ? 'big' : 'big low';
    let runningBadge = '';
    if (j.running_task) {
      runningBadge = `<span class="pill" style="background:#354e82;color:#fff;animation:pulse 1.5s infinite">
          ▶ running: ${j.running_task.task} (${j.running_task.started_ago_s}s)
        </span>`;
    }

    // Sparkline of pass/fail over last 30 episodes (oldest → newest, L→R)
    const hist = eps.slice().reverse();  // oldest first
    let bars = '';
    hist.forEach((e, i) => {
      const x = i * 6;
      const h = e.success ? 18 : 6;
      const y = 22 - h;
      const c = e.success ? '#5dd39e' : '#ff6b81';
      bars += `<rect x="${x}" y="${y}" width="5" height="${h}" fill="${c}"/>`;
    });
    const spark = `<svg width="${hist.length*6}" height="22" style="vertical-align:middle">${bars}</svg>`;

    document.getElementById('summary').innerHTML =
      `<span class="${rateCls}">${rate}%</span>` +
      `<span>success · last ${recent} eps</span>` +
      `<span style="color:var(--dim)">· ${total} total</span>` +
      `<span style="margin-left:6px">${spark}</span>` +
      runningBadge;

    // Cameras: bump query string to bust cache
    const t = Date.now();
    document.getElementById('cam-top').src = `/api/cam?name=top&t=${t}`;
    document.getElementById('cam-ego').src = `/api/cam?name=ego&t=${t}`;
    document.getElementById('cam-tp').src  = `/api/cam?name=tp&t=${t}`;

    // Pose
    const pk = document.getElementById('pose-kvs');
    pk.innerHTML = '';
    if (j.pose) {
      for (const [k, v] of Object.entries(j.pose)) {
        pk.innerHTML += `<span class="k">${k}</span><span class="v">${Number(v).toFixed(3)}</span>`;
      }
    }

    // Gauge truths
    const gk = document.getElementById('gauge-kvs');
    gk.innerHTML = '';
    if (j.gauges) {
      for (const [wall, g] of Object.entries(j.gauges)) {
        gk.innerHTML += `<span class="k">${wall}</span>` +
          `<span class="v">${Number(g.value).toFixed(2)} ${g.units}</span>`;
      }
    }

    // Stats
    const sk = document.getElementById('stats-kvs');
    sk.innerHTML = '';
    for (const [k, v] of Object.entries(j.stats || {})) {
      sk.innerHTML += `<span class="k">${k}</span><span class="v">${v}</span>`;
    }

    // Episodes
    const tb = document.querySelector('#ep-table tbody');
    tb.innerHTML = '';
    (j.episodes || []).forEach((e, i) => {
      const okCls = e.success ? 'ok' : 'fail';
      const okTxt = e.success ? '✓ pass' : '✗ fail';
      const age = Math.round((Date.now() / 1000 - e.ts) / 60);
      const link = e.eid
        ? `<a href="/api/transcript?f=${e.eid}.txt" target="_blank">log</a>`
        : '';
      tb.innerHTML += `<tr>
        <td>${e.n}</td>
        <td>${e.task} ${link}</td>
        <td class="${okCls}">${okTxt}</td>
        <td class="reward ${okCls}">${Number(e.reward).toFixed(2)}</td>
        <td>${Number(e.duration_s || 0).toFixed(0)}s</td>
        <td>${age}m ago</td>
        <td>${e.reason || ''}</td>
      </tr>`;
    });

    // Control Panel
    const c = j.components || {};
    const ctrl_el = document.getElementById('controls');
    const card = (key, label, sub, actions) => {
      const s = c[key] || {up: false, pids: []};
      const dot = `<span class="dot ${s.up ? 'up' : 'down'}"></span>`;
      const pids = s.pids && s.pids.length ? `PID ${s.pids.join(', ')}` : '';
      const btns = actions.map(a =>
        `<button class="${a.cls||''}" onclick="act('${key}','${a.op}'${a.extra||''})">${a.label}</button>`
      ).join('');
      return `<div class="ctrl"><div class="title">${dot}${label}<span style="font-size:10px;color:var(--dim)">${pids}</span></div>
        <div class="sub">${sub}</div>${btns}</div>`;
    };
    ctrl_el.innerHTML =
      card('sim', 'Simulation', 'MuJoCo server on :5556', [
        {op:'start',   label:'Start', cls:'primary'},
        {op:'stop',    label:'Stop',  cls:'danger'},
        {op:'restart', label:'Restart'},
        {op:'reset',   label:'Reset robot'},
      ]) +
      card('selfplay', 'Self-play loop', 'Runs Hermes episodes on Haiku', [
        {op:'start', label:'Run 10', cls:'primary', extra:',10'},
        {op:'start', label:'Run 30', cls:'primary', extra:',30'},
        {op:'stop',  label:'Stop',   cls:'danger'},
      ]) +
      card('viewer', 'MuJoCo Viewer', 'Native 3D window (60 fps)', [
        {op:'start', label:'Open viewer', cls:'primary'},
      ]) +
      card('autopush', 'GitHub auto-push', 'Syncs status/ every 10 min', [
        {op:'run',   label:'Sync now', cls:'primary'},
        {op:'start', label:'Enable schedule'},
        {op:'stop',  label:'Disable schedule', cls:'danger'},
      ]) +
      card('hermes_gw', 'Telegram gateway', '@billzhengbot listens for DMs', [
        // no controls — just status indicator
      ]);

    // Skills — highlight the card if edited in the last 5 min
    const sk_el = document.getElementById('skills');
    sk_el.innerHTML = '';
    const now = Date.now() / 1000;
    (j.skills || []).forEach(s => {
      const when = new Date(s.mtime * 1000).toLocaleString();
      const fresh = (now - s.mtime) < 300 ? 'fresh' : '';
      sk_el.innerHTML += `<div class="skill ${fresh}">
        <h3>${s.name}</h3>
        <div class="when">edited ${when} · ${s.size} bytes</div>
        <pre>${escapeHtml(s.body)}</pre>
      </div>`;
    });
  } catch (e) {
    document.getElementById('meta').textContent = 'error: ' + e;
  }
}
function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function act(component, op, rounds) {
  const toast = document.getElementById('toast');
  toast.textContent = `…${component}/${op}`;
  const body = rounds !== undefined ? JSON.stringify({rounds}) : null;
  try {
    const res = await fetch(`/api/control/${component}/${op}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: body,
    });
    const j = await res.json();
    toast.textContent = (j.ok ? '✓ ' : '✗ ') + (j.msg || '');
    setTimeout(tick, 400);    // refresh state after the action lands
  } catch (e) {
    toast.textContent = 'error: ' + e;
  }
}

tick();
setInterval(tick, 2000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

def _api_state() -> bytes:
    sim_alive = sim_call("ping", timeout=1.0).get("ok", False)
    pose = sim_call("get_pose", timeout=2.0).get("data") if sim_alive else None
    gauges = sim_call("all_gauges_truth", timeout=2.0).get("data") if sim_alive else None

    log = read_log()
    episode_ends = [e for e in log if e.get("event") == "episode_end"]
    episode_starts = [e for e in log if e.get("event") == "episode_start"]

    # Detect a currently-running episode: last start has no matching end
    running_task = None
    if episode_starts:
        last_start = episode_starts[-1]
        running_id = last_start.get("episode_id")
        if not any(e.get("episode_id") == running_id for e in episode_ends):
            running_task = {
                "task": last_start.get("task"),
                "started_ago_s": round(time.time() - last_start.get("ts", time.time()), 1),
            }

    # Per-task stats
    stats = {"total_episodes": len(episode_ends)}
    per_task: dict[str, dict] = {}
    for e in episode_ends:
        t = e.get("task", "?")
        s = per_task.setdefault(t, {"total": 0, "ok": 0, "r_sum": 0.0})
        s["total"] += 1
        if e.get("success"): s["ok"] += 1
        s["r_sum"] += float(e.get("reward", 0.0))
    for t, s in per_task.items():
        stats[f"{t}"] = f"{s['ok']}/{s['total']} ({s['ok']/max(1,s['total']):.0%})  avg_r={s['r_sum']/max(1,s['total']):+.2f}"

    # Latest 30 episodes
    latest = episode_ends[-30:][::-1]
    eps = [{
        "n": len(episode_ends) - (30 - i) if i < len(latest) else "?",
        "task": e.get("task", "?"),
        "success": bool(e.get("success")),
        "reward": e.get("reward", 0.0),
        "duration_s": e.get("duration_s", 0.0),
        "reason": e.get("reason", ""),
        "ts": e.get("ts", 0),
        "eid": e.get("episode_id", ""),
    } for i, e in enumerate(latest)]

    skills = read_skills()

    resp = {
        "sim_ok": sim_alive,
        "episode_count": len(episode_ends),
        "running_task": running_task,
        "pose": pose,
        "gauges": gauges,
        "stats": stats,
        "episodes": eps,
        "skills": [{"name": s["name"], "mtime": s["mtime"],
                    "size": s["size"], "body": s["body"]}
                   for s in skills],
        "components": component_status(),
    }
    return json.dumps(resp, default=str).encode()


def _api_cam(query: dict) -> tuple[bytes, str]:
    name = query.get("name", ["tp"])[0]
    r = sim_call("get_image", timeout=5.0, camera=name)
    if not r.get("ok"):
        # 1x1 transparent PNG fallback
        b = bytes.fromhex("89504e470d0a1a0a0000000d494844520000000100000001080600000015c14149000000014944415478da63600000000500017e8c04b00000000049454e44ae426082")
        return b, "image/png"
    return base64.b64decode(r["data"]["jpeg_base64"]), "image/jpeg"


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args): pass  # silence

    def do_GET(self) -> None:
        url = urllib.parse.urlparse(self.path)
        path = url.path
        query = urllib.parse.parse_qs(url.query)

        if path == "/" or path == "/index.html":
            body = DASHBOARD_HTML.encode()
            self._send(200, body, "text/html")
            return

        if path == "/api/state":
            self._send(200, _api_state(), "application/json")
            return

        if path == "/api/cam":
            body, ctype = _api_cam(query)
            self._send(200, body, ctype)
            return

        if path == "/api/transcript":
            fname = query.get("f", [""])[0]
            if not fname or "/" in fname or ".." in fname:
                self._send(400, b"bad", "text/plain")
                return
            p = TRANSCRIPT_DIR / fname
            if not p.exists():
                self._send(404, b"not found", "text/plain")
                return
            self._send(200, p.read_bytes(), "text/plain; charset=utf-8")
            return

        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        url = urllib.parse.urlparse(self.path)
        if not url.path.startswith("/api/control/"):
            self._send(404, b"not found", "text/plain")
            return
        # path: /api/control/<component>/<action>  (e.g. /api/control/sim/start)
        parts = url.path.strip("/").split("/")
        if len(parts) != 4:
            self._send(400, b"expect /api/control/<component>/<action>", "text/plain")
            return
        _, _, component, action = parts
        # Optional body with JSON args (e.g. {"rounds": 20})
        length = int(self.headers.get("Content-Length") or 0)
        args: dict = {}
        if length:
            try:
                args = json.loads(self.rfile.read(length).decode())
            except json.JSONDecodeError:
                args = {}
        result = do_action(component, action, rounds=int(args.get("rounds", 10)))
        self._send(200 if result.get("ok") else 500,
                   json.dumps(result).encode(), "application/json")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class ThreadedHTTP(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=5557)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    srv = ThreadedHTTP((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    logger.info("dashboard: %s  (sim expected at %s:%d)", url, SIM_HOST, SIM_PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
