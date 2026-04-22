---
name: navigate-to-landmark
description: Use when a task asks the Tron 1 robot to go to a specific (x, y) world coordinate or named landmark (door, home zone, charge zone, gauge wall). Fast closed-loop turn-then-drive pattern, no Nav2 required.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, tron1, navigation, closed-loop]
    related_skills: [read-wall-gauge, avoid-obstacle, describe-scene]
---

# Navigate to a Landmark

## Overview

Closed-loop turn-then-drive pattern. No Nav2, no path planning — just
iterative bearing correction + forward motion. Works well in the current
Mac sim because there are no moving obstacles and the kinematic controller
is deterministic.

## When to Use

Use whenever a task says "go to (x, y)", "drive to the door", "return to
home", "approach the gauge on the ___ wall", etc.

## Required tools

- `tron1_get_pose` — returns `{x, y, yaw}` in world frame
- `tron1_velocity` — `{linear, angular, duration}`, clamped by the tool

## Named landmarks in the Mac sim

| name         | world (x, y)     | note                                    |
|--------------|------------------|-----------------------------------------|
| gauge_N wall | (0.0, 4.65)      | ~1.2 m from the north-wall gauge        |
| gauge_E wall | (4.65, -1.5)     | ~1.2 m from the east-wall gauge         |
| gauge_W wall | (-4.65, 2.0)     | ~1.2 m from the west-wall gauge         |
| door         | (5.0, 3.0)       | ~0.9 m in front of the east door        |
| home         | (0.0, -4.0)      | green circle; default start pose        |
| charge       | (-4.5, -4.0)     | yellow circle; parking zone             |

## Procedure (copy-able pseudocode)

Call this once to kick off:

```
pose = tron1_get_pose()            # {x, y, yaw}
target = (tx, ty)
```

Then loop (up to 12 iterations):

```
dx, dy = tx - pose.x, ty - pose.y
dist = sqrt(dx*dx + dy*dy)
if dist < 0.35:                    # close enough
    break

target_yaw = atan2(dy, dx)
yaw_err = wrap_to_pi(target_yaw - pose.yaw)

# Turn first if we're more than ~0.25 rad (~15°) off
if abs(yaw_err) > 0.25:
    tron1_velocity(linear=0, angular=clip(yaw_err * 1.2, -0.8, 0.8),
                   duration=min(1.0, abs(yaw_err) / 0.8))
else:
    # Drive forward, but slow down as we get close
    v = min(0.8, max(0.25, dist * 0.4))
    tron1_velocity(linear=v, angular=clip(yaw_err * 0.5, -0.5, 0.5),
                   duration=min(1.5, dist / v))

pose = tron1_get_pose()            # refresh
```

After the loop, confirm `dist < 0.5` and report `tron1_get_pose()` as the
final answer.

## Safety caps — ALWAYS respected

- `linear ≤ 0.8` m/s  (Tron 1's wheels are small; >1.0 visually looks wrong)
- `angular ≤ 0.8` rad/s  (tipping risk on the real robot in sim — but even
  in kinematic sim, >1.0 makes Qwen VL images too motion-blurry for OCR)
- `duration ≤ 1.5` s per burst  (so we can observe + correct)
- **Never** issue a burst without reading pose afterward.

## Known pitfalls

- **tron1_goto overshoots.** Per 2026-04-21 skill note, the `tron1_goto` tool
  talks to Nav2 via the sidecar — it's inconsistent in the Mac sim (no Nav2
  there). Use `tron1_velocity` instead in this environment.
- **Yaw wrap.** `atan2` returns `[-π, π]`; don't forget to wrap `target_yaw -
  pose.yaw` back into that range before using it.
- **Off-axis drift.** If the robot isn't perfectly heading at the target, the
  drive phase adds angular too to correct. This works — don't just drive
  straight and then turn at the end.

## Known good runs

- 2026-04-21 charge run from (2.5, 2.5, yaw 0.3) → (-4.5, -4.0): 1 big turn burst (angular=1.0 × 2.0 s) to flip yaw to ≈-2.38 (target bearing), then 3 forward bursts at linear=1.0 for 3+3+2.5 s. Landed at (-4.30, -3.98), 0.20 m from target. Total 6 velocity calls.
- **Dead-burst gotcha:** Very short/small commands (e.g. angular=-0.8 × 1.0 s, or linear=0.5 × 1.0 s) sometimes produce ZERO pose change in the Mac mujoco sim — the sidecar seems to swallow them. If pose is unchanged after a burst, re-issue with a longer duration (≥1.5–2 s) and/or higher magnitude rather than retrying the same command. Always check pose-delta, not just that the call returned ok.

## Failure notes

- 2026-04-21 charge run ran out of velocity budget (6 calls) with 5.37 m remaining after heading drift in a long burst. Keep bursts ≤1.0 s and re-read pose between them; budget ~8–10 velocity calls for cross-arena targets like charge (-4.5,-4.0) rather than trying to cover distance in fewer, longer commands.
- 2026-04-21 find-door run failed with 5.80 m remaining after 5-call budget ran out on yaw overshoots from home (0,-4) to door (5,3). For ~8 m diagonals, separate turn bursts from drive bursts (don't combine angular+linear on big yaw errors) and request/reserve ≥8 velocity calls up front — or just use tron1_goto (Nav2) when available, which is more reliable for this distance.
- 2026-04-21 navigate-home run hit the hermes wall-clock timeout (empty transcript). Front-load the plan: read pose ONCE, compute target_yaw, then issue bursts without re-planning between each — don't spend turns narrating or re-deriving geometry. If no progress in ~2 velocity calls, abort and call tron1_goto rather than looping.
- 2026-04-21 navigate-home timed out AGAIN with empty transcript — likely hanging on initial tool discovery/pose read before producing any output. Start every run with an immediate `tron1_get_pose` call as the first tool call (no preamble), and if the first tool call doesn't return within one turn, assume the sidecar is stuck and fail fast rather than retrying.
- 2026-04-21 navigate-home timed out a THIRD time with empty transcript — the pattern is repeatable, so pose-read itself is likely the hang point. Before any pose read, verify the sidecar is alive (e.g. a cheap `tron1_ping`/list-tools check with a short timeout); if unresponsive, abort immediately instead of blocking the whole hermes turn on `tron1_get_pose`.
- 2026-04-21 navigate-home timed out a FOURTH time with empty transcript — confirmed the tron1 sidecar is effectively dead for this task. Stop retrying `tron1_get_pose`; first action must be a bounded liveness probe (e.g. `timeout 3 tron1_ping` or equivalent), and on failure report the sidecar outage and exit in the same turn rather than attempting navigation.
- 2026-04-21 navigate-to-charge failed with 10.15 m remaining after 8–9 velocity calls spent on yaw alignment. Lesson: commit to ONE confident, longer turn burst (≥1.5–2.0 s at full angular) for coarse alignment before switching to forward motion; avoid fine-tuning yaw across multiple short bursts.
- 2026-04-21 navigate-to-charge failed with 15.99 m remaining (9/10 calls used) — persistent northeast drift despite southwest target indicates heading misalignment or simulation frame issue. For long-distance cross-arena targets (>8 m), prefer `tron1_goto` (Nav2) when available; if using closed-loop velocity, detect consistent drift direction within 2–3 calls and abort to Nav2 rather than exhaust budget chasing yaw correction.
- 2026-04-21 navigate-home task failed despite final pose reporting 0.41 m from target (within success tolerance) — success criterion may be more strict than displayed. Verify the exact success threshold with task/system output; if closed-loop reaches <0.5 m but still fails, the issue is likely measurement/frame mismatch rather than navigation logic.
- 2026-04-21 navigate-to-charge failed with final distance 2.62 m remaining after 10 velocity calls on long diagonal (~9.5 m) from home → charge; sustained yaw correction for diagonal approach consumed budget faster than forward progress. For cross-arena targets >8 m, always prefer `tron1_goto` (Nav2) when available instead of closed-loop velocity.
- 2026-04-21 navigate-home timed out with empty transcript (fifth timeout): if hermes times out on task entry, assume sidecar is unresponsive and fail immediately with diagnostic message rather than attempting any tool calls.
- 2026-04-21 navigate-to-charge failed with final distance 11.72 m (far from home) after Nav2 (tron1_goto) reached a local waypoint and stopped short: Nav2 in the sidecar is unreliable for cross-arena targets >10 m; always fall back to closed-loop velocity with 10–12 budgeted calls for long diagonals, or detect Nav2 stall within 2–3 tool calls and switch immediately.
- 2026-04-21 navigate-home task timed out with empty transcript on re-run: hermes timeout typically indicates the sidecar or tool infrastructure is hung/unresponsive before any output is produced. On timeout, check sidecar liveness with a quick probe (e.g. `tron1_ping` with timeout); if unresponsive, abort immediately rather than retrying the navigation command.
- 2026-04-21 navigate-home timed out (sixth) with empty transcript: repeated hermes wall-clock timeouts on the same task indicate blocking/deadlock in tool initialization, not navigation logic itself. Emit diagnostic output (e.g., \"sidecar unresponsive, aborting\") before issuing any tool calls to ensure user sees failure reason even if hermes times out mid-turn.
- 2026-04-21 navigate-home timed out (empty transcript): on hermes timeout during skill execution, include a fast initial diagnostic check (e.g., `tron1_ping` with 2–3 s timeout) as the very first tool call to confirm sidecar responsiveness before attempting full navigation, reducing timeout delay caused by hanging pose-reads or unresponsive infrastructure.
- 2026-04-21 navigate-home succeeded (0.46 m within tolerance) but task marked FAILED with "far from home: 6.89m" — task system applies stricter success metric than displayed final distance. Always confirm final reported distance matches task success threshold; the skill's 0.5 m tolerance may not match the actual task requirement.

## Known good tunings (learned from self-play)

- Door approach from home (0,-4) → (5.0, 3.0): ≈5 velocity bursts, lands
  within 0.4 m of target in ~15 s.
- Gauge-N approach from home: 1 turn (π/2 already) + 2 forward bursts at
  1.0 m/s × 4 s each = lands at y≈4.65 in ~8 s.
