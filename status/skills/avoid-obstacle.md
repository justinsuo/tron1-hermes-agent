---
name: avoid-obstacle
description: Use when the Tron 1 robot needs to move but there's a detected obstacle in its path. Chooses a safe sidestep + continue, or halts + asks for help when there's no good path.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, tron1, navigation, safety]
    related_skills: [read-wall-gauge, describe-scene]
---

# Avoid Obstacle

## Overview

Defensive navigation helper: called before any `tron1_velocity` move or
`tron1_goto` when the local map shows a likely obstruction. Either plans
a sidestep or aborts with a useful explanation.

Nav2's local planner already avoids obstacles during goal pursuit — this skill
is for the cases where the agent is issuing velocity-level commands directly
and needs to stay safe.

## When to Use

Use when:

- About to issue `tron1_velocity(linear > 0, ...)` and `tron1_get_detections`
  shows any detection with label in `{box, person, chair, cone, door, wall}`
  at an estimated distance < 0.8 m.
- About to execute a skill that involves forward motion.

Skip when:

- Goal pose is set via `tron1_goto` — Nav2 handles it.
- Robot is stationary and will not move.

## Procedure

1. **Assess.**
   Call `tron1_get_detections` (JSON string → parse). Build a list of obstacles
   within a 0.8 m radius ahead of the robot's current heading. For each, note
   `(class, distance_m, bearing_deg)`.

2. **Decide.**
   - If **no obstacles** within 0.8 m: return `{safe: true}`.
   - If **one obstacle** within 0.3–0.8 m and `|bearing_deg| < 30`: return
     `{safe: false, action: "sidestep", angular: 0.4*sign(bearing_deg opposite), duration: 0.5}`.
   - If **obstacle < 0.3 m** or **multiple clustered obstacles**: return
     `{safe: false, action: "halt", reason: "<human-readable>"}` and do NOT
     move. Ask the user for guidance.

3. **Optional vision check (low confidence detections).**
   If any relevant detection has `confidence < 0.6`, call `tron1_get_image`
   and `qwen_vl_local` with prompt:
   > "Is there any obstacle within 1 meter directly ahead of the camera? Answer with one of: CLEAR | SIDESTEP_LEFT | SIDESTEP_RIGHT | HALT, then a brief reason."

4. **Act (only if caller requested it).**
   - `sidestep`: `tron1_velocity(linear=0, angular=<signed>, duration=0.5)`
     followed by `tron1_velocity(linear=0.2, duration=0.8)`.
   - `halt`: publish a zero Twist via `tron1_velocity(0,0,0.1)` and log.

## Guarantees

- **Never** issues motion when the obstacle is within 0.3 m.
- **Never** publishes angular speed above 0.6 rad/s (below sim/Nav2 tipping
  risk for the Tron 1 wheeled biped).
- Logs every halt event to the robotics log with
  `{task: "avoid-obstacle", success: true, obs: {detections}, action: "halt"}`
  so the self-play loop can surface repeated failure scenes for more training.

## Open questions to improve later

- Depth from the RGBD camera isn't wired into `tron1_get_detections` yet; we
  estimate distance from bbox area, which is noisy for unknown objects.
  Add `tron1_get_depth` sidecar op once the sim publishes `/depth`.
- Obstacle class list is hard-coded. A future version should read it from
  `~/.hermes/skills/robotics/avoid-obstacle/obstacles.yaml`.
