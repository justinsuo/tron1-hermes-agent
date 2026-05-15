# Changelog

All notable changes to this project. Format roughly follows [Keep a Changelog](https://keepachangelog.com/),
with engineering war stories included because they make this stack make sense.

## [Unreleased]

### Documentation
- Rewrote `README.md` to be comprehensive (architecture diagram, module map, design principles, roadmap, acknowledgments).
- Added `ARCHITECTURE.md` with a deep technical dive.
- Added `CONTRIBUTING.md` with development setup + style conventions.
- Added this `CHANGELOG.md`.

---

## 2026-05-15 — stability week

After overnight self-play sessions started crashing the host Mac
(WindowServer freezing, forced power-cycle, no kernel-panic file), a
six-commit forensic chain landed all the underlying GPU/VRAM bugs.

### `d3e7e04` — fix: dedicated render worker thread so cameras actually render

The "persistent renderer" fix broke the camera images because on macOS
MuJoCo's `Renderer` binds its GL context to the thread that created it.
With `ThreadingMixIn` spawning a fresh handler thread per TCP connection,
the renderer worked the first time (created in thread A) and then
silently hung on every subsequent call from threads B/C/D — observed as
`get_image` returning zero bytes, dashboard falling back to the 1×1
transparent PNG, no error in the log.

Fix: a singleton render worker thread that exclusively owns the GL
context. All `Sim.get_image()` callers enqueue a job onto a
`queue.Queue` and wait on a `threading.Event`. Worker is started in
`Sim.__init__` and lives for the duration of the sim.

### `69a5e5a` — fix: dashboard caused crashes by hammering sim renderer

Crash #5 happened right after opening the dashboard. Root cause: the
dashboard JS was firing **3 camera image fetches every 2 seconds** —
1.5 renders/sec from the browser alone — which compounded with
self-play's own vision calls on the sim's single-locked renderer.

Three-layer fix:
- Server-side cache + rate limit on `/api/cam`: each camera
  re-rendered at most once every `TRON1_DASH_CAM_TTL_S` seconds (default
  5). Verified with a 20-call torture test: 20 fetches in 0.44 s, sim
  renderer hit once.
- JS staggers fetches: one of {top, ego, tp} per tick, rotating.
  Combined with the 4s tick (slowed from 2s), the dashboard requests
  ≤0.083 cam/sec per camera.
- New `?nocams=1` URL toggle disables all camera fetches for safe
  stats-only viewing.

Combined dashboard load reduced ~30x.

### `a20447f` — fix: stop renderer churn — root-cause the system-hang bug

After the 4th forced reboot, discovered that the "persistent renderer"
optimization from the previous fix was being defeated by
`reset_robot()` defaulting to `regen_gauges=True` — that flag triggers
`_rebuild_model()`, which reloads the MJCF and destroys+rebuilds the
MuJoCo Renderer. Every single episode was tearing down and reallocating
GL textures, even though the renderer field *looked* persistent in code.

Combined with Apple Silicon's lazy GL texture release behavior, wired
GPU memory grew unbounded until WindowServer hung.

Fixes:
- `selfplay/tasks.py`: `reset_robot()` default `regen_gauges` flipped
  True → False.
- `selfplay/robotics_selfplay.py`: regen explicitly every 30 episodes
  via a module-level counter.
- `sim/sim.py`: `gc.collect()` after explicit `close()`+drop of the
  renderer; new `health` sidecar op returning `{rss_mb, renderer_alive,
  render_h, render_w, pid, ts}`.

Verified leak-free with a 110-call torture test:
```
   10 captures           → 873 MB
   60 captures           → 875 MB  (+2 MB across 50 caps)
   60 cap + 30 resets    → 893 MB  (+18 MB across 30 reset cycles)
   + 1 explicit regen    → 894 MB  (+1 MB — the slow path)
```

### `3a76e90` — fix: aggressive duty-cycle reduction to stop crash loop

After three forced reboots in 24 hours confirmed the issue was Apple
Silicon GPU/VRAM saturation under sustained mixed load (not RAM
exhaustion — 48 GB total is plenty), four cuts applied together:

1. LLM: Qwen3-8B-4bit → Qwen3-4B-4bit (4.9 GB → 2.7 GB resident).
2. Sim render: 640×480 → 320×240 (4× fewer pixels, 5× smaller JPEG).
3. Self-play cadence: BATCH_ROUNDS 50→20, BATCH_DELAY 8s→20s.
4. launchd auto-restart: `RunAtLoad` and `KeepAlive` flipped to false
   so a forced reboot no longer re-triggers the heavy stack.

### `4284546` — fix: persistent MuJoCo renderer to stop GPU context churn

Root cause of the periodic full-system hangs during overnight self-play:
`sim.py` was creating a fresh `mujoco.Renderer` per `get_image()`
request and relying on `close()`+GC to release the underlying GL
textures. On Apple Silicon the GPU shares VRAM with system RAM, and
renderer construction allocates faster than the driver reclaims — after
~30-60 min of 50-episode batches with multiple ego/tp captures, VRAM
saturates and WindowServer freezes.

Fix: one Renderer per `Sim` instance, guarded by the existing `_lock`.
Rebuilt only when `regen_gauges=True` reloads the MJCF.

Also wired the locomotion layer to real WF_TRON1A robot state:
- Sim exposes `get_initial_pose`, `get_imu`, `get_joint_state` ops.
- `observation_builder.py` `JOINT_ORDER` is now the actual 8
  WF_TRON1A actuated joints (abad/hip/knee/wheel × 2).
- `fake_policy_runner.py` and `policy_runner.py` defaults updated to
  `action_dim=8, obs_dim=33`.

### `c4d4aaf` — feat: add locomotion layer + `tron1_walk_command` tool

Introduces a clean boundary between Hermes-level intent and low-level
control, inspired by the LimX RL stack (`tron1-rl-isaacgym`,
`pointfoot-legged-gym`) without copying any of their code.

New package `locomotion/`:
- `policy_interface.py` — abstract `PolicyInterface` ABC.
- `fake_policy_runner.py` — safe zero-action runner that echoes the
  velocity command for the existing kinematic backend.
- `policy_runner.py` — lazy torch loader for `.pt` checkpoints,
  raises `PolicyLoadError` gracefully if torch is missing or the
  checkpoint is malformed.
- `observation_builder.py` — LimX-style obs vector
  `[base_ang_vel, projected_gravity, joint_pos_rel, joint_vel,
  last_action, command, gait_clock?]` with DR noise hook.
- `command_adapter.py` — `SafetyLimits` + `LocomotionCommand` +
  clipping.
- `locomotion_logger.py` — JSONL log at `~/.tron1-locomotion-log.jsonl`.

New Hermes tool `hermes_tools/tron1_locomotion_tool.py` exposes
`tron1_walk_command(vx, vy, yaw_rate, duration)`.

New self-play module `selfplay/locomotion_tasks.py` adds six tasks
exercising the new tool (walk-forward-1m, turn-to-heading,
approach-wall-gauge, stop-at-viewing-distance,
navigate-around-obstacle, return-home-with-locomotion).

New skill markdown:
- `skills/locomotion-commanding.md`
- `skills/approach-distance.md`
- `skills/recovery-after-motion-failure.md`

Plus tests under `tests/` (pytest, 40 cases, all green) covering
command clipping, fake runner output shape, observation builder layout,
locomotion logger JSONL writing, `tron1_walk_command` mocked end-to-end,
and missing/garbage checkpoint failure modes.

---

## 2026-04-30 — local LLM stack restored

After repeated mlx_lm.server crashes and a launchd PATH bug that was
causing all self-play episodes to fail with `hermes CLI not on PATH`,
the stack came back online on Qwen 3 8B 4-bit, with the launchd plist
patched to include `/Users/justinsuo/.local/bin` in `PATH`.

## 2026-04-22 — first overnight self-play

First successful 5-hour overnight self-play session. ~370 total
episodes, 33–50% success rate on the most reliable tasks. Skill files
auto-grew as the agent reflected on its own failures.

## 2026-04-21 — initial release

Mac-native MuJoCo simulation with the real WF_TRON1A meshes, Hermes
agent driving via `tron1_*` tools, browser dashboard, three-layer
self-healing (launchd → bash supervisor → batch loop), clickable
`Tron 1.app`, GitHub auto-push every 10 min.
