# Tron 1 Mac-native Simulation

A MuJoCo simulation that runs **directly on macOS** (no Ubuntu VM, no ROS 2)
and speaks the same TCP JSON protocol as the VM-side `~/ros2_sidecar/sidecar.py`.

The Hermes `tron1_*` tools connect to this sim identically to how they'd
connect to the real Tron 1 — so everything you build against it ports
unchanged when the VM/Jetson is available.

## Quick start

```bash
# 1. Start the sim (leave this running in a terminal)
~/.hermes/hermes-agent/venv/bin/python ~/tron1-sim-mac/sim.py

# 2. In another shell, run the demo
~/.hermes/hermes-agent/venv/bin/python ~/tron1-sim-mac/demo.py
```

The demo:
1. Resets the robot to start pose `(0, -4, yaw=+90°)`.
2. Reads the scene (detections with distance/bearing).
3. Drives the robot forward ~8 m until 1.1 m from the gauge.
4. Grabs the ego camera frame.
5. Runs Qwen 2.5 VL 3B (local MLX) on the frame.
6. Compares the reading to sim ground truth.

Typical output (gauge randomized each launch):

```
== step 5: Qwen VL reads the gauge ==
   qwen: {"value": 78.0, "units": "°C", "confidence": 0.99}
   latency: 425 ms
== step 6: compare to sim ground truth ==
   truth: value=74.55 units=°C
```

## Controlling from Hermes interactively

```bash
hermes
> use the tron1_* tools to drive forward 2 meters and describe what you see
```

If you get "sidecar unreachable" errors, the sim isn't running or not on port
5556. Start it with `python ~/tron1-sim-mac/sim.py` and retry.

## Scene

`assets/scene.xml` — a 12 m × 12 m room with:
- **Ground**: checker floor with cross markers
- **Walls**: tan plaster (N/E/W), brick (S)
- **Gauge**: a 1.2 m × 1.2 m plane on the north wall, procedurally retextured
  each sim launch via `gauge_render.py`. Ground-truth reading written to
  `assets/gauge_truth.json`.
- **Obstacles**: 2 orange boxes + 1 cone
- **Door**: dark wood panel on the east wall
- **Robot**: simplified holonomic box (not the Tron 1 biped) with an ego
  camera at z=0.45. Kinematic control via qpos writes — no walking policy
  needed to drive the loop.

Swap in the full [`WF_TRON1A` MJCF](~/tron1_ws/src/robot-description/pointfoot/WF_TRON1A/xml/robot.xml)
once the pre-trained RL walking policy is wired up.

## Protocol

Listens on `127.0.0.1:5556` (one JSON per line). Extended from the VM
sidecar's protocol with these extras:

| op            | effect                                           |
|---------------|--------------------------------------------------|
| `reset`       | reset robot to start pose                        |
| `gauge_truth` | return ground-truth gauge reading (for grading)  |

All the standard sidecar ops work too: `ping`, `publish_command`,
`publish_cmd_vel`, `publish_goal`, `get_pose`, `get_scene`, `get_detections`,
`get_image`, `list_topics`.

## With the MuJoCo viewer

```bash
python ~/tron1-sim-mac/sim.py --viewer
```

Opens the MuJoCo passive viewer in a native macOS window — you can watch the
robot drive while Hermes controls it from the other terminal. (Slower than
headless mode since the viewer drives physics at real-time instead of
stepping lazily.)

## Known limits

- **Kinematic, not dynamic** — the robot pose is integrated from velocity
  commands directly. Collisions are computed for rendering but don't affect
  motion. Fine for vision training; swap in dynamics + a walking policy
  before expecting realistic force interactions.
- **MuJoCo Renderer is not thread-safe** on macOS — `sim.py` creates a fresh
  renderer per `get_image` call. Adds ~20 ms per frame; acceptable for
  ≤30 Hz capture.
- **No depth / lidar topics yet** — only RGB. Extending `get_depth` is a
  ~30-line sidecar addition (MuJoCo renderer supports depth natively).
- **Scene is hand-authored** — no procedural randomization of obstacle
  layout or lighting yet. Add a `--randomize` flag that perturbs geom
  positions before rendering to generate harder training data.

## Integration with the rest of the stack

```
~/tron1-selfplay/robotics_selfplay.py  ──►  hermes (one-shot task)
                                              │
                                              ▼
                              tron1_* tools (Hermes tools)
                                              │
                                              ▼  TCP 5556
                                           sim.py (this folder)
                                              │
                                              ▼
                                     MuJoCo physics + render
                                              │
                                              ▼
                                         camera JPEG
                                              │
                                              ▼
                              qwen_vl_local tool (MLX Qwen 2.5 VL)
```

Self-play loop:
```
python ~/tron1-selfplay/robotics_selfplay.py --rounds 20 --backend mujoco-mac
python ~/tron1-selfplay/dashboard.py
```
