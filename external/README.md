# External References

This directory holds **read-only references** to upstream projects that we draw
architectural inspiration from but deliberately do **not** vendor into this
repo. Each reference should be added as a git submodule, never copied.

## tron1-rl-isaacgym

LimX's official RL training stack for the Tron 1 / point-foot family. Trains
low-level locomotion policies (PPO + Isaac Gym) that output joint torques /
positions from a fixed observation vector. The trained `.pt` checkpoint is
the artifact we eventually want to load through
[`locomotion/policy_runner.py`](../locomotion/policy_runner.py).

```bash
# Run from the repo root
git submodule add https://github.com/limxdynamics/tron1-rl-isaacgym \
    external/tron1-rl-isaacgym
git submodule update --init --recursive
```

Also useful and architecturally similar:

```bash
git submodule add https://github.com/limxdynamics/pointfoot-legged-gym \
    external/pointfoot-legged-gym
```

## Why submodule and not copy?

- **License hygiene** — the LimX repos carry their own license; vendoring would
  pull license obligations into this repo.
- **Drift** — the upstream observation order and reward terms evolve. Mirroring
  by submodule lets us pin a commit and upgrade deliberately.
- **Footprint** — Isaac Gym depends on CUDA + Linux. We don't want our macOS
  development environment to require either.

## What we copy *patterns* from, not code

- Observation vector layout: `[base_ang_vel, projected_gravity, joint_pos -
  default_joint_pos, joint_vel, last_action, command]` plus optional gait
  clock features. See [`observation_builder.py`](../locomotion/observation_builder.py).
- Domain randomization placeholders: friction, mass, motor strength,
  observation noise. We don't *train* with these in MuJoCo today but we hook
  the same knobs into the env so sim-to-real handoff stays plausible.
- Action-rate-penalty reward shaping ideas inform the grading in
  [`selfplay/locomotion_tasks.py`](../selfplay/locomotion_tasks.py).

## Graceful absence

Nothing in this repo `import`s anything from `external/` directly. If the
submodule is missing the rest of the system still runs — we'll just fall back
to the kinematic MuJoCo backend and the [fake policy
runner](../locomotion/fake_policy_runner.py).
