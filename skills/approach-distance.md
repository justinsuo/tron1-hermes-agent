---
name: approach-distance
description: How close to stand when looking at a wall gauge, sign, or door. Stopping too close clips the target out of frame; stopping too far makes the vision model guess.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, tron1, vision, approach]
    related_skills: [read-wall-gauge, locomotion-commanding]
---

# Approach distance

When the task requires *reading* something (a gauge dial, a sign, a door
state), the goal is **not** to touch the object — it is to frame the
object cleanly for `qwen_vl_local`.

## Recommended stand-off distances

| Target           | Sweet-spot range | Why |
|------------------|------------------|-----|
| Wall gauge       | **1.0 – 1.3 m**  | full circular dial fits the camera frame |
| Door             | **0.8 – 1.2 m**  | door + jamb visible; agent can see open/closed state |
| Floor obstacle   | **0.5 – 0.8 m**  | enough for bbox identification, far enough to side-step |
| Scene snapshot   | **3.0 – 5.0 m**  | wide context for `describe-scene` |

## Procedure (gauges)

1. Read pose. Compute Euclidean distance to the target landmark.
2. Issue `tron1_walk_command` bursts toward the target.
3. **Before each burst, check distance remaining.** Stop driving when
   you are between 1.0 m and 1.3 m of the gauge centerline.
4. Capture an image with `tron1_get_image`. If the dial edge is clipped
   or the dial occupies < 1/3 of the frame width, back up 0.2 m and
   try again.
5. Run `qwen_vl_local` on the framed image.

## Common mistakes

- Driving until you "feel close" — at 0.4 m the dial is half-cropped.
  Use **explicit distance math** from `tron1_get_pose`, not vibes.
- Stopping further than 1.5 m and asking the vision model to read a
  needle — it will guess and you will be graded as wrong.
- Approaching a wall gauge head-on so the floor checker pattern crowds
  out the dial — angle yourself so the gauge fills the upper-center of
  the frame.

## When the visible-region check fails

If `qwen_vl_local` returns "needle position unclear" or "dial partially
visible":
  - back up 0.3 m,
  - re-capture,
  - if still unclear, try a yaw adjustment of ±10° to reduce parallax.
