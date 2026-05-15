# Architecture

This document goes one layer below the README's hand-wavy diagram. If
you want to understand why each component is shaped the way it is — or
hack on it — start here.

## 1. The three loops

```
LOOP 1 (every minute):  the agent ReAct loop
    Hermes → tool call → sim/vision response → next tool call → …

LOOP 2 (every episode, ~30-90 s):  the self-play loop
    sample task → reset sim → run agent → grade → log → reflect on failure

LOOP 3 (every 10 min): the GitHub sync loop
    snapshot stats/skills/transcripts → commit → push to origin/main
```

Each outer loop wraps the one inside. The dashboard at `:5557` is just a
read-only window into the JSONL logs they produce.

## 2. Why a sim sidecar over TCP?

The Hermes CLI is a fresh Python subprocess per episode. Importing
`mujoco` + loading the MJCF + creating an `MjModel` takes ~500-800 ms.
If every Hermes call paid that cost, an 8-tool episode would be
~6 seconds of import overhead alone.

So the sim runs as a separate **long-lived process** with a tiny
TCP-JSON protocol on `127.0.0.1:5556`. Every Hermes tool that needs sim
state opens a fresh TCP connection, sends one JSON line, reads one JSON
line back, closes. Connections are cheap (~1 ms loopback) and the
sim's `MjModel` lives for the whole self-play session.

### Why TCP and not Unix-domain sockets?

It's a Mac-local stack today, but the same protocol talks to the ROS 2
sidecar on the real Tron 1's Jetson Orin. TCP makes the network/local
boundary identical. Localhost loopback on macOS is functionally as fast
as UDS for this volume.

## 3. The render-worker thread (and why it took 6 commits to get right)

The sim runs `ThreadingMixIn` + `TCPServer`, so each TCP connection
gets its own request-handler thread. That's correct for **most** sim
ops — `get_pose`, `ping`, `all_gauges_truth`, `health` — they just read
data from `MjData` under a single lock and return.

But `get_image` calls `mujoco.Renderer.render()`, and on macOS the
**Renderer's OpenGL context is bound to the thread that created it**.
A Renderer created in thread A and called from thread B silently hangs
— no exception, no log entry, just zero bytes back to the client.

This was the bug behind ~four forced reboots. The fix went through
four iterations:

1. **Per-request Renderer** (original): worked but caused GPU memory leak.
   Each request constructs a Renderer (allocates framebuffer + textures
   in VRAM), Apple Silicon's GL driver lazily releases textures, after
   ~30-60 min of self-play VRAM saturates and WindowServer hangs.

2. **Persistent Renderer guarded by `_lock`**: would have worked if
   only one thread ever called `render()`. But `ThreadingMixIn` means
   different threads were trying to use the same Renderer's GL context,
   which silently hangs on macOS.

3. **Don't rebuild renderer on `_rebuild_model()`**: discovered after
   re-introducing the bug — `regen_gauges=True` (default!) was calling
   `_rebuild_model()` every reset, which destroyed and recreated the
   renderer. Flipped `regen_gauges` default to False; regenerate every
   30 episodes instead.

4. **Singleton render-worker thread** (current): a dedicated thread
   that exclusively owns the Renderer + GL context. Every
   `get_image()` call enqueues a job on a `queue.Queue` and waits on a
   `threading.Event`. The worker thread pulls one job at a time,
   renders, signals the caller. Thread-safe by construction.

The worker is started in `Sim.__init__` and runs for the life of the
sim. On `_rebuild_model()` we close the renderer and let the worker
recreate it on the next call.

## 4. The locomotion boundary

The LLM is **never** allowed to command joint torques. The boundary is
`tron1_walk_command(vx, vy, yaw_rate, duration)`:

```python
# Hermes side
result = tron1_walk_command(vx=0.4, yaw_rate=0.1, duration=1.0)
# {ok: true, command: {...}, start_pose: {...}, end_pose: {...},
#  distance_moved: 0.38, fell: false, collided: false}
```

```
Hermes call
   │
   ▼
CommandAdapter.build(...)   ← clip vs SafetyLimits
   │
   ▼
ObservationBuilder.build(...)   ← LimX-style obs vector
   │
   ▼
PolicyInterface.act(obs, command)
   ├─ FakePolicyRunner  (today, returns velocity-echo action)
   └─ PolicyRunner      (later, loads a trained .pt)
   │
   ▼
sim sidecar: publish_cmd_vel(linear=vx, angular=yaw_rate, duration=...)
   │
   ▼
Kinematic backend integrates pose, returns start/end delta
   │
   ▼
LocomotionLogger.end(...)   ← JSONL record
   │
   ▼
Structured result back to Hermes
```

Switching from fake → real policy is **purely** a runner swap. No
other code changes:

```bash
export TRON1_POLICY_CHECKPOINT=/path/to/walk_v0.pt
# restart hermes
```

Inside `tron1_locomotion_tool.py`:

```python
checkpoint = os.getenv("TRON1_POLICY_CHECKPOINT")
if checkpoint:
    try:
        runner = PolicyRunner(checkpoint)
    except PolicyLoadError as e:
        logger.warning("policy load failed (%s) — falling back to fake", e)
        runner = FakePolicyRunner()
else:
    runner = FakePolicyRunner()
```

See [`docs/locomotion_integration.md`](docs/locomotion_integration.md)
for the LimX-vs-this-repo split.

## 5. The dashboard's three rate limits

The dashboard at `:5557` polls `/api/state` for stats and
`/api/cam?name=…` for each camera image. Without rate-limiting, an open
tab adds ≥1.5 renders/sec to the sim, which compounds with self-play's
own vision calls and crashes Apple Silicon.

Three layers of throttling protect the renderer:

1. **Server-side cache** in `_api_cam`: each camera's last JPEG is
   cached for `TRON1_DASH_CAM_TTL_S` seconds (default 5). Subsequent
   requests within that window return the cached payload without
   touching the sim. A "stale marker" prevents two concurrent misses
   from both hitting the sim.

2. **Client-side staggering**: the JS rotates through `top → ego → tp`
   one camera per tick instead of fetching all three each tick. Full
   rotation = `tick_ms * 3` (12 s at the default 4 s tick).

3. **Slower tick**: `tick_ms` went from 2000 → 4000.

Combined: dashboard-induced renderer load is ~0.083 renders/sec per
camera, vs ~1.5 originally. **30× lower.**

Escape hatch: `http://127.0.0.1:5557/?nocams=1` disables all camera
fetches entirely for safe stats-only viewing.

## 6. Self-play episode lifecycle

```
robotics_selfplay.run_one():
    task    = sample_task(weighted, failure-boosted)
    reset_robot(task.reset_to,
                regen_gauges=(episode_count % 30 == 0))
    eid     = robotics_log.start_episode(task.id)

    transcript, rc = run_hermes(task.prompt, task.budget_s)
                     # subprocess.run([hermes, chat, -q PROMPT, -Q,
                     #                  -m mlx-community/Qwen3-4B-4bit,
                     #                  -t tron1,vision_local,skills])

    truth   = gather_sim_truth()       # gauges, pose at finish
    success, reward, reason = task.grade(transcript, truth)

    robotics_log.end_episode(success, reward, reason, evidence=[...])

    if not success:
        reflect_on_failure(task.id, reason, transcript[-400:])
        # one short turn, --max-turns 6, skill_manage(action="patch")
        # → appends a lesson under "Failure notes" in the relevant SKILL.md

    write_transcript(eid, transcript)
```

Graders live in `selfplay/tasks.py` (legacy 7 tasks) and
`selfplay/locomotion_tasks.py` (6 new locomotion tasks). They query
sim ground truth via the same TCP protocol as Hermes and return
`(success: bool, reward: float, reason: str)`.

## 7. The launchd plist (and why it's currently off)

`scripts/com.justinsuo.tron1-supervisor.plist` registers a launchd
service that runs `selfplay/supervisor.sh`. Normally:

- `RunAtLoad=true`: starts when the agent is loaded.
- `KeepAlive=true`: re-spawns if supervisor exits.
- `ThrottleInterval=60`: 60-second cooldown to prevent rapid-fire restart loops.

Combined with `supervisor.sh`'s own auto-restart of self-play batches,
this gave three layers of self-healing. **However**, after the Apple
Silicon GPU-saturation crashes, both flags were flipped to `false` to
make sure a forced reboot doesn't drag the heavy stack back up while
the user is trying to do other things. To re-enable:

```bash
# edit scripts/com.justinsuo.tron1-supervisor.plist
# flip RunAtLoad + KeepAlive back to true
launchctl load -w ~/Library/LaunchAgents/com.justinsuo.tron1-supervisor.plist
```

Manual start: `bash selfplay/supervisor.sh`.

## 8. The auto-push loop

A separate launchd job (`com.justinsuo.tron1-autopush.plist`) runs
`scripts/auto_push.sh` every 10 minutes:

```
scripts/sync_to_repo.sh
    cp sim/sim.py dashboard/dashboard_server.py selfplay/* etc.
    cp ~/.hermes/skills/robotics/*/SKILL.md skills/
    tail -500 ~/.tron1-robotics-log.jsonl > status/episodes_recent.jsonl
    cp $TRANSCRIPTS_DIR/*.txt status/transcripts/   (last 10)
    snapshot 3 camera JPEGs from sim → status/cam_*.jpg
    regenerate status/stats.md + stats.json
    regenerate README.md via scripts/render_readme.py
git commit -am "auto: sync · N episodes · R% recent · F files"
git push origin main
```

This is why GitHub's README always shows the latest stats and why
SKILL.md edits made by the agent show up as commits — `git blame
skills/read-wall-gauge.md` will tell you which episode taught it that
lesson.

## 9. File-format contracts

The pieces of state that flow through the system are deliberately
plain-text/JSONL so anyone can inspect them with `cat` and `jq`:

- `~/.tron1-robotics-log.jsonl` — one line per
  `{event: episode_start | episode_end}` record. Schema in
  `selfplay/robotics_log.py`.
- `~/.tron1-locomotion-log.jsonl` — one line per locomotion command.
  Schema in `locomotion/locomotion_logger.py`.
- `~/.hermes/skills/robotics/*/SKILL.md` — the agent's procedural
  memory. YAML frontmatter + markdown body.
- `status/stats.json` — machine-readable rollup of total episodes,
  per-task success rate, average reward.
- `status/live.json` — current pose + gauge readings at sync time.

If any of these format contracts change, search-and-replace covers the
whole stack; no schema registry needed.

## 10. The 3 tests that matter

```bash
~/.hermes/hermes-agent/venv/bin/python -m pytest tests -q
# 40 passed in 0.43s
```

Coverage by what would actually break if the test failed:

- `test_command_adapter.py` — make sure `SafetyLimits` clips outrageous
  velocity commands before they reach the sim. Catches "LLM hallucinated
  vx=15.0".
- `test_fake_policy_runner.py` — runner output shape stays compatible
  with the kinematic backend.
- `test_observation_builder.py` — the LimX-style obs vector layout
  doesn't drift accidentally. Catches "someone added a slot in the
  middle".
- `test_locomotion_logger.py` — JSONL writes don't get tangled by
  concurrent calls; fell-detection threshold works.
- `test_policy_runner.py` — graceful failure when the `.pt` is missing
  or malformed. Catches "real policy crashed Hermes".
- `test_walk_command.py` — `tron1_walk_command` returns sensible
  structured results end-to-end (with mocked sidecar).

There is no test for the sim itself — its behavior is verified by the
hourly self-play runs that drop transcripts in `status/transcripts/`.

## Further reading

- [`docs/locomotion_integration.md`](docs/locomotion_integration.md) — LimX RL stack vs this repo
- [`locomotion/README.md`](locomotion/README.md) — locomotion package internals
- [`external/README.md`](external/README.md) — how to submodule the LimX repos
- [`CHANGELOG.md`](CHANGELOG.md) — what's changed and when, with reasons
