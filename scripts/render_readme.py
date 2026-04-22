#!/usr/bin/env python3
"""Regenerate ~/tron1-hermes-agent/README.md with the latest stats embedded.
Invoked by sync_to_repo.sh on every auto-push cycle.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

REPO = Path("/Users/justinsuo/tron1-hermes-agent")
STATUS = REPO / "status"

stats: dict = {}
sp = STATUS / "stats.json"
if sp.exists():
    try:
        stats = json.loads(sp.read_text())
    except json.JSONDecodeError:
        stats = {}

total = stats.get("total", 0)
rate = stats.get("recent_rate_pct", 0)
per_task = stats.get("per_task", {})
ts = stats.get("ts", time.time())

# Rank tasks by success rate desc
ranked = sorted(
    per_task.items(),
    key=lambda kv: kv[1].get("rate_pct", 0),
    reverse=True,
)

task_rows = []
for name, s in ranked:
    task_rows.append(
        f"| `{name}` | {s['ok']}/{s['total']} | **{s['rate_pct']:.0f}%** | {s['avg_reward']:+.2f} |"
    )

live_text = ""
live_p = STATUS / "live.json"
if live_p.exists():
    try:
        live = json.loads(live_p.read_text())
        g = live.get("gauges", {})
        p = live.get("pose", {})
        bits = []
        if p:
            bits.append(f"**pose** `({p.get('x',0):+.2f}, {p.get('y',0):+.2f}, yaw={p.get('yaw',0):+.2f})`")
        if g:
            bits.append("**gauges** " + " · ".join(
                f"{wall}={t.get('value','?'):.2f} {t.get('units','')}"
                for wall, t in g.items()
            ))
        if bits:
            live_text = "  \n".join(bits)
    except Exception:
        pass

updated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

readme = f"""# Tron 1 · Hermes Agent

**A self-improving robotics AI agent running live on Mac.** The Hermes agent drives the LimX Tron 1 through a MuJoCo simulation, reads analog gauges with a local vision model (Qwen 2.5 VL on MLX), and teaches itself between runs by editing its own skill files. No cloud APIs for vision, no Unity/Unreal, no ROS 2 on the Mac — everything runs natively.

[![demo](sim/demo_drive.gif)](sim/demo_drive.mp4)

> *6-second clip: Tron 1 driving in the simulation. Bent-knee standing pose matches the real WF_TRON1A; wheels rotate visually at ω=v/r as the base moves. Full MP4: [`sim/demo_drive.mp4`](sim/demo_drive.mp4).*

---

## Live progress

*Auto-updated every ~10 minutes. Last sync: **{updated}**.*

**{total} total episodes · {rate:.0f}% success on the last 30**

{live_text}

### Per-task breakdown

| task | ✓ / total | success % | avg reward |
|---|---|---|---|
{chr(10).join(task_rows) if task_rows else "| _no episodes yet_ |  |  |  |"}

See [`status/stats.md`](status/stats.md) for the full episode log and
[`status/transcripts/`](status/transcripts/) for what the agent actually said in each run.

### Live camera snapshots

| top-down | ego | chase |
|---|---|---|
| ![top](status/cam_top.jpg) | ![ego](status/cam_ego.jpg) | ![chase](status/cam_tp.jpg) |

---

## What is this?

A complete, working Mac-native robotics agent stack:

- **Simulation** ([`sim/`](sim/)) — MuJoCo with the actual WF_TRON1A meshes, 3 procedurally-rendered analog gauges on different walls, obstacles, and a door. Kinematic base control (no walking policy needed) with visually spinning wheels.
- **Hermes tools** ([`hermes_tools/`](hermes_tools/)) — `tron1_*` tools that drive the robot (`tron1_velocity`, `tron1_goto`, `tron1_get_image`, …) plus `qwen_vl_local` for on-device vision with MLX.
- **Self-play harness** ([`selfplay/`](selfplay/)) — 7-task bank with per-task graders that query the sim for ground truth. Failed episodes trigger a 60-second reflection pass where Hermes patches the relevant SKILL.md with one actionable lesson.
- **Live dashboard** ([`dashboard/`](dashboard/)) — browser-viewable at http://127.0.0.1:5557/ when running locally. Shows live camera feeds, episode history, skill files with edit timestamps, and a pass/fail sparkline.
- **Skills** ([`skills/`](skills/)) — the agent's procedural memory. These files grow as the agent self-reflects on failures.
- **ROS 2 sidecar** ([`ros2_sidecar/`](ros2_sidecar/)) — the matching VM-side / real-Tron 1 bridge so the same Hermes tools work on the physical robot.
- **Training** ([`training/`](training/)) — MLX LoRA fine-tune pipeline for Qwen 2.5 VL on synthetic gauge images.

---

## Run it yourself

```bash
# One-command bring-up (sim + dashboard)
./scripts/start_all.sh

# With the MuJoCo native viewer
./scripts/start_all.sh viewer

# With self-play running too
./scripts/start_all.sh selfplay 20
```

Then open **http://127.0.0.1:5557/** in a browser.

Full setup notes in [`DELIVERY.md`](DELIVERY.md).

---

## The self-learning proof

Every time an episode fails, Hermes gets one cheap turn with just the `skills` toolset and a prompt like:

> *"A previous run of task X just FAILED (reason Y). Append ONE concise actionable bullet to `~/.hermes/skills/robotics/Z/SKILL.md` under a `Lessons` or `Failure notes` section..."*

The agent calls `skill_manage(action="patch")` and writes back a lesson it
extracted from the transcript. Next session reads the updated SKILL.md and
behavior changes — no retraining, no gradient step, just markdown getting
smarter over time.

**Concrete example** (from the current `read-wall-gauge.md`):

> *"Suspiciously round values (exact multiples of 10/100) often indicate the VLM snapped to a major tick instead of interpolating; on round outputs, always re-capture from a 15° offset or 20 cm closer and average."*

The current [`skills/read-wall-gauge.md`](skills/read-wall-gauge.md) contains **16 agent-authored lessons** like this, covering specific VLM failure modes on different gauge types. That file was ~3 KB when seeded; it's now 10+ KB.

---

## Repo layout

```
.
├── DELIVERY.md            # Full deliverable doc
├── README.md              # Auto-regenerated with latest stats (this file)
├── sim/                   # MuJoCo sim + scene + demo video
├── dashboard/             # HTTP progress dashboard
├── selfplay/              # Task bank, graders, self-play loop
├── hermes_tools/          # Hermes-callable tron1_* + qwen_vl_local
├── skills/                # Robotics SKILL.md files (the agent's procedural memory)
├── training/              # MLX LoRA pipeline
├── ros2_sidecar/          # VM / real-robot ROS 2 bridge
├── scripts/               # start_all.sh, sync/auto-push
└── status/                # Auto-updated every 10 min:
    ├── stats.md           #   human-readable scoreboard
    ├── stats.json         #   machine-readable
    ├── episodes_recent.jsonl  # last 500 episode records
    ├── cam_top.jpg        #   live top-down view
    ├── cam_ego.jpg        #   live robot POV
    ├── cam_tp.jpg         #   live chase view
    ├── skills/            #   snapshot of SKILL.md files
    └── transcripts/       #   last 10 Hermes episode transcripts
```

---

## License

MIT — see [LICENSE](LICENSE). Built on top of:

- [LimX WF_TRON1A MJCF + meshes](https://github.com/limxdynamics/tron1-mujoco-sim) (BSD-3)
- [Nous Research · Hermes Agent](https://github.com/NousResearch/hermes-agent) (MIT)
- [MLX-VLM](https://github.com/Blaizzy/mlx-vlm) (MIT)
"""

(REPO / "README.md").write_text(readme)
print(f"[readme] wrote {REPO/'README.md'}")
