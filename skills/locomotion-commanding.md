---
name: locomotion-commanding
description: How to issue velocity / yaw-rate commands to the Tron 1 robot via tron1_walk_command. Closed-loop pattern: command → re-read pose → adjust → command. Never assume a command moved the robot.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, tron1, locomotion, closed-loop]
    related_skills: [approach-distance, recovery-after-motion-failure, navigate-to-landmark]
---

# Locomotion commanding

How to drive the Tron 1 robot in a stable, observable way using
`tron1_walk_command`. This replaces direct use of `tron1_velocity` for
multi-step navigation.

## Required tools

- `tron1_walk_command(vx, vy, yaw_rate, duration)` — high-level locomotion.
  Clipped to vx ≤ 0.8 m/s, vy ≤ 0.4 m/s, yaw_rate ≤ 0.8 rad/s, duration ≤ 2 s.
- `tron1_get_pose` — read current `{x, y, z, yaw}`.

## Core pattern: command → observe → adjust

1. Read pose. Note (x₀, y₀, yaw₀).
2. Decide a SHORT command. Prefer **duration ≤ 1.5 s**, not 2.0 s.
3. Call `tron1_walk_command(...)`.
4. Read pose again. Compare to (x₀, y₀, yaw₀). Did the robot actually move?
5. Adjust the next command based on what really happened, not what you
   intended.

## Rules of thumb

- **Short bursts beat long bursts** near obstacles, near visual targets,
  and when correcting heading.
- **Small yaw corrections** near a target — large yaw bursts often
  motion-blur the next camera frame and waste a vision call.
- **Don't combine large vx with large yaw_rate** in the same burst. Turn
  first (vx≈0), then drive (yaw_rate≈0).
- **If you overshoot, reduce duration before reducing velocity.** Halving
  duration is more accurate than halving vx, because clipping rounds vx.

## Failure recognition

`tron1_walk_command` returns `{distance_moved, yaw_change, fell, collided}`.
If `distance_moved` is < 0.05 m after a command you expected to move,
treat it as a dead burst:
  - re-issue with **longer duration** (not larger vx),
  - or check sidecar reachability via `tron1_ping`.

`fell` means the base z dropped — abort the task and call
`recovery-after-motion-failure`.

## Don't do this

- Don't issue 5 commands in a row without reading pose between them.
- Don't request `vx=2.0` or `yaw_rate=3.0` — they get clipped, and the
  grader penalizes the unsafe request even when the clip saved you.
- Don't assume "I sent the command" means "the robot moved." The sim
  occasionally swallows tiny commands.
