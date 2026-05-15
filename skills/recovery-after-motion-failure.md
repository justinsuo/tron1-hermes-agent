---
name: recovery-after-motion-failure
description: What to do when tron1_walk_command returns fell=true, collided=true, or distance_moved≈0. Sequence pose-read → image-check → small corrective motion → resume task.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, tron1, recovery, error-handling]
    related_skills: [locomotion-commanding, navigate-to-landmark]
---

# Recovery after motion failure

When a locomotion command misbehaves, **stop, look, then move**. Do not
loop on the same failing command.

## Symptom → response table

| Symptom                              | First response |
|--------------------------------------|----------------|
| `distance_moved` ≈ 0                 | call `tron1_get_pose` to confirm. Then re-issue with **longer duration**, not larger vx. |
| `fell=true`                          | abort the task. Report failure. Do not attempt walk commands until a reset. |
| `collided=true`                      | reverse 0.3 m (`vx=-0.3, duration=1.0`), read pose, then yaw ~30° away from obstacle. |
| Sidecar `error: sidecar unreachable` | call `tron1_ping`. If still down, emit a diagnostic message and stop — do NOT keep retrying. |
| Pose shows wrong heading             | correct yaw first (`vx=0, yaw_rate=±0.4`), then drive forward. |
| Robot is too close to a wall         | back up SLOWLY (`vx=-0.2, duration=0.5`), read pose, then turn before moving forward. |

## Three-step recovery (most failures)

1. **Sense.** Always call `tron1_get_pose` + `tron1_get_image` first.
   Don't guess what the robot's state is.
2. **Diagnose.** Compare actual pose to expected pose. Is the yaw off by
   more than 0.2 rad? Is the base z below 0.5? Is there an obstacle in
   the camera frame?
3. **Correct.** Issue ONE small command that addresses the diagnosis.
   Then return to the main task loop.

## When to give up

- If `fell=true`: give up immediately. Do not attempt to right the robot
  via velocity commands — the kinematic backend can't fall, but a real
  policy might be in an unrecoverable pose.
- If three consecutive commands all return `distance_moved < 0.05`:
  give up. The infrastructure is wedged. Emit a diagnostic and exit.
- If `qwen_vl_local` keeps returning "image too dark" or "no scene":
  the camera is occluded — back up 0.5 m before retrying.

## Don't do this

- Don't retry the exact same command after a failure — change *something*.
- Don't issue a long burst (duration > 1.5 s) immediately after a fall
  or collision. Use a 0.5 s probing burst first.
- Don't combine recovery with progress in the same command — separate
  "stand up / back up" from "go toward goal".
