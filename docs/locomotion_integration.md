# Locomotion integration

How the `tron1-hermes-agent` repo relates to the LimX RL stack, and where
the boundaries are.

## Two repos, two jobs

| Repo | Role | Lives where |
|------|------|-------------|
| **`tron1-hermes-agent`** (this repo) | High-level cognition: planning, tool use, vision, self-play, skill memory. | macOS dev box, runs Hermes + MuJoCo. |
| **`limxdynamics/tron1-rl-isaacgym`** (and `pointfoot-legged-gym`) | Low-level locomotion training. Produces `.pt` checkpoints. | Linux + CUDA machine (separate). Referenced as a git submodule under [`external/`](../external/README.md). |

The two never share a Python process. The interface between them is the
trained `.pt` checkpoint — that's it.

## Architectural rule

> The LLM does not control joint torques. The LLM controls *intent*. The
> locomotion layer translates intent into low-level control.

The boundary lives at `tron1_walk_command(vx, vy, yaw_rate, duration)`.

```
                          ┌──────────────────────────────────┐
   Hermes LLM ───────►    │   tron1_walk_command tool         │
   (chat / self-play)     │   (hermes_tools/...)              │
                          └─────────┬────────────────────────┘
                                    │ CommandAdapter (clip)
                                    ▼
                          ┌──────────────────────────────────┐
                          │   PolicyInterface                 │
                          │   ├─ FakePolicyRunner  (today)    │
                          │   └─ PolicyRunner (.pt)  (later)  │
                          └─────────┬────────────────────────┘
                                    │ action vector
                                    ▼
                          ┌──────────────────────────────────┐
                          │   Sim backend                     │
                          │   ├─ MuJoCo kinematic  (today)    │
                          │   └─ ROS 2 / real robot  (later)  │
                          └──────────────────────────────────┘
```

## What's swappable, what's stable

**Stable** (don't change without a migration plan):

- The Hermes tool name: `tron1_walk_command`.
- Its argument schema: `vx`, `vy`, `yaw_rate`, `duration`.
- The `PolicyInterface` ABC.
- The `LocomotionLogger` JSONL schema.

**Swappable**:

- `FakePolicyRunner` → `PolicyRunner("/path/to/policy.pt")` once a
  trained checkpoint exists.
- MuJoCo kinematic backend → ROS 2 sidecar → real robot. The sim
  protocol on port 5556 stays identical.

## Today's state (Stage-1 baseline)

- `FakePolicyRunner` is wired in. It returns zero-ish actions and echoes
  the velocity command for the kinematic backend.
- `MuJoCo kinematic` backend ignores joint-level actions; the sim's
  `publish_cmd_vel` op consumes `(linear, angular, duration)`.
- `tron1_walk_command` therefore behaves like a safer wrapper around
  `tron1_velocity` with logging, observation building, and pose
  delta reporting.

## Future state (post-checkpoint)

- Train a policy in the LimX submodule (Isaac Gym + PPO, off-Mac).
- Export with `torch.jit.script(actor)` so `PolicyRunner` can load it.
- Set `TRON1_POLICY_CHECKPOINT=/path/to/policy.pt` and restart Hermes.
- No code changes in this repo.

## What we explicitly do not do

- **No Isaac Gym in this repo.** It would force CUDA + Linux on the
  dev box.
- **No ROS 2 install on macOS.** Real-robot control still goes through
  [`ros2_sidecar/`](../ros2_sidecar/).
- **No joint-torque tools exposed to the LLM.** The temptation to do
  this for "expressivity" is wrong — the LLM is bad at high-frequency
  control loops.
- **No vendoring of upstream LimX code.** Submodule only.

## Domain-randomization hooks

`ObservationBuilder` supports gaussian noise on the observation vector,
and `domain_randomize_defaults()` perturbs the default joint pose. These
are stand-ins for the full DR sweep that runs in Isaac Gym training. We
don't *train* in MuJoCo, but exposing the same knobs makes it less
surprising when a real policy is dropped in.

Sim-side DR (friction, mass, motor lag) is not yet implemented in the
MuJoCo backend — it doesn't matter for the kinematic mode, but will
matter once `PolicyRunner` is the runner. Tracked as a TODO in
[`locomotion/observation_builder.py`](../locomotion/observation_builder.py).

## Logs

- Hermes-level outcomes: `~/.tron1-robotics-log.jsonl` (already used by
  `selfplay/robotics_log.py`).
- Locomotion-level commands: `~/.tron1-locomotion-log.jsonl` (new).

The dashboard can `tail` both. The reflection pass on failed episodes
already edits `~/.hermes/skills/robotics/*/SKILL.md` to capture lessons;
the new locomotion skill files now participate in that loop.

## How to use the new tool

In a Hermes chat or self-play prompt:

```
Use tron1_walk_command(vx=0.4, vy=0, yaw_rate=0, duration=1.5) to drive
forward, then call tron1_get_pose to check progress.
```

In Python (for tests or one-off scripts):

```python
from hermes_tools.tron1_locomotion_tool import _handle_walk_command
print(_handle_walk_command({"vx": 0.4, "duration": 1.0}))
```

## Where to go next

- Add a proper sim backend for joint-level action consumption (so
  `PolicyRunner` can actually be exercised end-to-end on macOS).
- Pin the LimX submodule to a known-good commit.
- Capture pose at episode start in the sim's `reset` op so the
  `walk-forward-1m` grader has a true reference point.
