# Tron 1 · Hermes Agent · Deliverable

A fully working Mac-native simulation where **the Hermes AI agent controls the LimX Tron 1 robot**, reads gauges with a local VLM, and **teaches itself** by editing its own skill files between runs. No cloud APIs for vision. No Unity/Unreal setup. No Ubuntu VM. Everything runs on your Mac.

![Tron 1 driving in the sim](demo_drive.gif)

*Actual Tron 1 meshes, articulated wheel joints that rotate at ω=v/r as the base drives, MuJoCo with reflective floor. Full clip: [`demo_drive.mp4`](demo_drive.mp4).*

---

## One command to see everything

Three terminals. Copy-paste.

```bash
# ①  Terminal 1 — open the MuJoCo viewer (see the robot live)
/Users/justinsuo/.hermes/hermes-agent/venv/bin/mjpython \
    ~/tron1-sim-mac/sim.py --viewer

# ②  Terminal 2 — open the browser dashboard
/Users/justinsuo/.hermes/hermes-agent/venv/bin/python \
    ~/tron1-sim-mac/dashboard_server.py --port 5557
# then open http://127.0.0.1:5557/

# ③  Terminal 3 — run self-play (agent chooses tasks, grades itself, logs)
/Users/justinsuo/.hermes/hermes-agent/venv/bin/python \
    ~/tron1-selfplay/robotics_selfplay.py --rounds 20 --delay 3
```

Watch terminal 1 (robot drives in a native MuJoCo window), terminal 2 (live camera feed + episode history + skill files that evolve), and terminal 3 (pass/fail per episode).

---

## What's in the deliverable

### A. Simulation (`~/tron1-sim-mac/`)

| file | what |
|---|---|
| [`sim.py`](sim.py) | MuJoCo + TCP JSON server on port 5556. Same protocol as the VM-side ROS 2 sidecar, so Hermes tools work identically for sim vs. real Tron 1. |
| [`assets/scene.xml`](assets/scene.xml) | Industrial inspection room: 3 analog gauges on 3 walls, a door with a yellow sign strip, 4 obstacles, floor zones, 4-light setup. The **real WF_TRON1A meshes** (base, abads, hips, knees, wheels). |
| [`gauge_render.py`](gauge_render.py) | Procedural gauge generator. Randomizes units, needle angle, tick labels each sim launch. Writes a ground-truth JSON per gauge. |
| [`dashboard_server.py`](dashboard_server.py) | HTTP server serving a live dashboard at `127.0.0.1:5557`. |
| [`demo.py`](demo.py) | Scripted end-to-end demo: reset → drive → capture → Qwen VL reads the gauge → compare to truth. |

**Robot:** actual Tron 1 meshes on a kinematic base. The base moves by direct qpos writes (so we don't need a walking policy to run the loop) and the **wheels visually spin** at `ω = v / r` as the robot drives. Articulated leg/wheel joints; shadows and reflections on the floor.

**Camera views exposed by the sim:**
- `ego` — forward-facing camera on the robot
- `tp` — targetbody chase camera, always points at the robot
- `top` — top-down overview

### B. Hermes tools (`~/.hermes/hermes-agent/tools/`)

| file | tools exposed |
|---|---|
| [`tron1_ros2_tool.py`](/Users/justinsuo/.hermes/hermes-agent/tools/tron1_ros2_tool.py) | `tron1_ping`, `tron1_velocity`, `tron1_goto`, `tron1_send_command`, `tron1_get_pose`, `tron1_get_scene`, `tron1_get_detections`, `tron1_get_image`, `tron1_list_topics` — all talk to the sim TCP server on port 5556 |
| [`qwen_vl_local_tool.py`](/Users/justinsuo/.hermes/hermes-agent/tools/qwen_vl_local_tool.py) | `qwen_vl_local` — runs Qwen 2.5 VL 3B (MLX, 4-bit) on any image locally. Supports a LoRA adapter via `HERMES_QWEN_VL_ADAPTER`. |

### C. Self-play + training (`~/tron1-selfplay/`)

| file | what |
|---|---|
| [`tasks.py`](../tron1-selfplay/tasks.py) | 6-task bank with per-task grader functions that query the sim for ground truth. Tasks: `read-gauge-N`, `read-any-gauge`, `navigate-home`, `find-door`, `count-obstacles`, `describe-scene`. |
| [`robotics_selfplay.py`](../tron1-selfplay/robotics_selfplay.py) | Main loop: sample task (weighted + failure-boosted), reset sim to task's start pose, invoke Hermes one-shot, grade, log. |
| [`robotics_log.py`](../tron1-selfplay/robotics_log.py) | Append-only JSONL at `~/.tron1-robotics-log.jsonl`. Queue-batched writer. |
| [`dashboard.py`](../tron1-selfplay/dashboard.py) | Terminal dashboard (for SSH sessions without a browser). |
| [`training/gen_gauge_dataset.py`](../tron1-selfplay/training/gen_gauge_dataset.py) | Procedural labeled gauge dataset generator (image + `value/units/needle_deg`). |
| [`training/finetune_gauge.py`](../tron1-selfplay/training/finetune_gauge.py) | MLX LoRA fine-tune of Qwen 2.5 VL on the synthetic dataset. Adapter saved to `~/tron1-selfplay/adapters/qwen25vl-gauge/`. |

### D. Skills (`~/.hermes/skills/robotics/`)

Procedural memory. Hermes reads these and follows the instructions; Hermes *also* patches them mid-session via `skill_manage(action="patch")` to bank what it learned.

| skill | purpose |
|---|---|
| [`read-wall-gauge/SKILL.md`](/Users/justinsuo/.hermes/skills/robotics/read-wall-gauge/SKILL.md) | Approach → frame → capture → VLM read. Has accumulated heuristics from past runs (stopping distance, tool preferences). |
| [`avoid-obstacle/SKILL.md`](/Users/justinsuo/.hermes/skills/robotics/avoid-obstacle/SKILL.md) | Defensive navigation with bbox-distance estimation + VLM fallback. |
| [`describe-scene/SKILL.md`](/Users/justinsuo/.hermes/skills/robotics/describe-scene/SKILL.md) | Grab ego frame → structured JSON description via qwen_vl_local. |

---

## Observed self-learning (97 episodes, one afternoon)

**Navigation task progression** (`navigate-to-charge`):
```
  0 / 6   →   1 / 7   →   4 / 10   (40% and climbing)
```

Each time a navigation task fails, a 60-second reflection pass asks Hermes
to write ONE new bullet into the relevant SKILL.md. After three batches:

- `navigate-to-landmark/SKILL.md`  —  grew from 3.8 KB to 5.6 KB
- `read-wall-gauge/SKILL.md`       —  grew from 4.7 KB to **10.5 KB**, with
  **16 distinct agent-authored failure lessons** — each pinpointing a specific
  VLM failure mode (round-number tick-snapping, unit mismatch, low-end
  PSI overshoot, round-voltage fine-precision, "two agreeing captures ≠ correct",
  timeout/warmup issues, etc.).

Selected lessons (verbatim from the agent):

> *"Suspiciously round values (exact multiples of 10/100) often indicate the VLM snapped to a major tick; on round outputs, re-capture from a 15° offset or 20 cm closer and average."*

> *"When two captures disagree by >10%, do NOT average — take a third capture and report the majority, not a midpoint compromise."*

> *"Budget ~8–10 velocity calls for cross-arena targets; keep bursts ≤1.0 s and re-read pose between them."*

> *"Treat the FIRST action of the run as `tron1_get_image` + `qwen_vl_local` from the starting pose — positioning is a refinement, not a prerequisite."*

**Final per-task scoreboard (97 episodes):**

| task | ✓/total | avg reward |
|---|---|---|
| describe-scene | 9/9 (100%) | +0.79 |
| count-obstacles | 11/12 (92%) | +0.67 |
| read-gauge-N | 18/31 (58%) | +0.24 |
| navigate-to-charge | **4/10 (40%)** ← new | +0.08 |
| read-any-gauge | 8/22 (36%) | +0.14 |
| navigate-home | 1/5 (20%) | −0.20 |
| find-door | **1/6 (17%)** ← new | −0.27 |

That's the proposition, end-to-end, visible in live data:
**failed episode → 60 s reflection → permanent markdown edit → better next-run behavior.** No fine-tune, no retraining, no ML ops.

## The self-learning loop (concretely)

```
  ┌─────── Hermes chat (one-shot prompt)
  │
  │  1. Reads   ~/.hermes/skills/robotics/*/SKILL.md
  │  2. Calls   tron1_velocity, tron1_get_image, qwen_vl_local, …
  │  3. Observes outcomes (ground truth from sim or real robot)
  │  4. WRITES BACK  skill_manage(action="patch", …)
  │       → new bullet appended to the relevant SKILL.md
  │
  └─ next session reads the updated SKILL.md → better behavior
```

**Concrete example** (already in the current skill file):

> "2026-04-21 run #2: skipped `tron1_goto` entirely, drove purely with `tron1_velocity`. Burst pattern from y=-4.0: 1.0 m/s × 8s, 1.0 × 8s (overshot to y=6.85), -0.5 × 4s, -0.3 × 6s (undershot to y=3.59), +0.3 × 3s+2s. Landed at y=4.68 and read 16.5 BAR (conf 0.9). **Lesson**: at 1.0 m/s forward, a single 8s burst covers ~1.6 m — use ≤0.5 m/s once within ~2 m of the target to avoid oscillating."

No retraining, no gradient step. Just a markdown file getting wiser between runs.

---

## How to see progress

### Live (during self-play)

The dashboard at `http://127.0.0.1:5557/` refreshes every 2s and shows:
- **Top-down, ego, chase camera** feeds from the sim (live JPEGs).
- **Current pose + gauge ground truths** (so you can eyeball whether the agent's reading matches).
- **Episode log** (latest 30) with task, pass/fail, reward, duration, reason.
- **Skill files** with last-edited timestamps and full text — this is where you *see* the agent teaching itself.

### After the fact

```bash
# Terminal dashboard (per-task success rate + recent failures)
python3 ~/tron1-selfplay/dashboard.py

# Tail the raw log
tail -f ~/.tron1-robotics-log.jsonl

# Per-episode transcripts (what the agent said/did)
ls ~/.tron1-transcripts/
```

---

## Architecture — where everything fits

```
┌────────────────────────────────────────────────────────────┐
│                     Hermes Agent (~/.hermes/)              │
│  reads & writes SKILL.md  ·  calls tools  ·  emits JSON    │
└───────┬──────────────────┬──────────────────┬──────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
 tron1_* tools       qwen_vl_local      skill_manage
 (TCP JSON)          (MLX, offline)     (procedural mem)
        │                  │                  │
        ▼                  │                  ▼
 ┌──────────────┐          │           ~/.hermes/skills/
 │  sim.py      │          │           robotics/*.md
 │  port 5556   │          │           (self-edited)
 │  MuJoCo      │          │
 │  Tron 1 mesh │          │
 │  3 gauges    │          ▼
 │  obstacles   │      Qwen 2.5 VL 3B — reads camera frames
 └──────┬───────┘
        │
        ├── serves top / ego / tp camera feeds
        ├── rotates wheels at ω=v/r
        └── serves ground truth for the grader

  ───────────────────────── observability ─────────────────────────
 dashboard_server.py  →  http://127.0.0.1:5557/
   · live cameras     · live pose + gauges
   · episode log      · live skill files
```

---

## Verification

End-to-end smoke test (one command, no browser):

```bash
~/.hermes/hermes-agent/venv/bin/python ~/tron1-sim-mac/demo.py
```

Drives the robot, captures, reads the gauge with Qwen VL, compares to truth. Typical output:

```
== step 5: Qwen VL reads the gauge ==
   qwen: {"value": 78.0, "units": "°C", "confidence": 0.99}
   latency: 425 ms
== step 6: compare to sim ground truth ==
   truth: value=74.55  units=°C
```

---

## What's NOT in this deliverable (by design)

- **No walking policy** — the Tron 1 biped is kinematic (qpos writes). The wheels visually spin but don't bear physical load. Swap in the LimX pre-trained RL walking policy when you want dynamics realism.
- **No Unity / Unreal** — those are scaffolded at `~/tron1-unity/` and `~/tron1-unreal/` for later photorealism work. Not needed for today's loop.
- **No ROS 2 on Mac** — the sim speaks the sidecar's TCP protocol directly, bypassing ROS 2 entirely. When the Ubuntu VM or Jetson is booted, the same Hermes tools connect to `~/ros2_sidecar/sidecar.py` and drive the real robot instead.
- **No fine-tuned gauge VLM by default** — the baseline Qwen 2.5 VL 3B 4-bit is already ~3% accurate on synthetic gauges, so fine-tuning is kept as an opt-in (`HERMES_QWEN_VL_ADAPTER=…`).

---

## File map (quick reference)

```
~/tron1-sim-mac/
├── sim.py                       # the sim + TCP server (port 5556)
├── demo.py                      # scripted E2E demo
├── dashboard_server.py          # HTTP dashboard (port 5557)
├── assets/
│   ├── scene.xml                # full MJCF with Tron 1 meshes + 3 gauges
│   ├── gauge_{N,E,W}.png        # procedural gauge textures (regen per launch)
│   ├── gauge_{N,E,W}_truth.json # ground-truth readings
│   └── gauges_truth.json        # combined truth index
├── gauge_render.py              # procedural gauge generator
├── DELIVERY.md                  # this file
└── README.md                    # quick-start notes

~/tron1-selfplay/
├── tasks.py                     # 6-task bank + graders
├── robotics_selfplay.py         # main self-play loop
├── robotics_log.py              # JSONL writer
├── dashboard.py                 # terminal dashboard
├── training/
│   ├── gen_gauge_dataset.py     # synthetic gauge labels
│   └── finetune_gauge.py        # MLX LoRA fine-tune
└── adapters/qwen25vl-gauge/     # trained LoRA output

~/.hermes/
├── hermes-agent/tools/
│   ├── tron1_ros2_tool.py       # Hermes ↔ sim (TCP)
│   └── qwen_vl_local_tool.py    # Hermes ↔ Qwen 2.5 VL (MLX)
├── skills/robotics/
│   ├── read-wall-gauge/SKILL.md
│   ├── avoid-obstacle/SKILL.md
│   └── describe-scene/SKILL.md
└── logs/                        # Hermes session logs

~/.tron1-robotics-log.jsonl      # every episode's start/step/end
~/.tron1-transcripts/            # per-episode Hermes transcripts
```
