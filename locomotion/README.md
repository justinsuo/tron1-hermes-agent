# `locomotion/` — low-level layer for the Tron 1 Hermes agent

The Hermes LLM never controls joint torques directly. It calls velocity /
goal tools, and this package translates those into either a kinematic
backend (today) or an RL-policy backend (later).

```
Hermes
  └─ tron1_walk_command(vx, vy, yaw_rate, duration)
       └─ CommandAdapter.build(...)           # clip vs SafetyLimits
            └─ ObservationBuilder.build(...)  # raw state → policy obs
                 └─ PolicyInterface.act(...)  # Fake or trained .pt
                      └─ sim/robot backend     # MuJoCo today, real robot later
                           └─ LocomotionLogger.end(...)   # JSONL record
```

## Modules

| File | Purpose |
|------|---------|
| `policy_interface.py` | Abstract policy contract (`reset`, `act`, `get_metadata`). No torch/Isaac dependency. |
| `fake_policy_runner.py` | Safe zero-action stand-in. Echoes the velocity command so the kinematic backend still moves. |
| `policy_runner.py` | Lazy torch loader for LimX-style `.pt` checkpoints. Raises `PolicyLoadError` on missing file / incompatible format. |
| `observation_builder.py` | Assembles `[base_ang_vel, projected_gravity, joint_pos_rel, joint_vel, last_action, command, gait_clock?]`. |
| `command_adapter.py` | `SafetyLimits` + `LocomotionCommand` + `CommandAdapter`. |
| `locomotion_logger.py` | Append-only JSONL log of every command. |

## What's intentionally missing

- Joint-torque control. We don't expose torque outputs to the LLM.
- Isaac Gym imports. Training stays in the external submodule.
- Real-robot direct drivers. Real deploys go through the existing
  [`ros2_sidecar/`](../ros2_sidecar/) bridge.

## Switching from fake to trained policy

```python
# Today (no .pt available):
runner = FakePolicyRunner(action_dim=10, obs_dim=48)

# Once you have a LimX checkpoint:
from locomotion import PolicyRunner, PolicyLoadError
try:
    runner = PolicyRunner("~/policies/tron1_walk_v0.pt",
                          obs_dim=48, action_dim=10)
except PolicyLoadError as e:
    print(f"[locomotion] fallback to fake: {e}")
    runner = FakePolicyRunner(action_dim=10, obs_dim=48)
```

Both runners satisfy `PolicyInterface`, so the Hermes tool layer does not
need to change.
