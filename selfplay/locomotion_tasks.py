"""Self-play tasks that exercise the new locomotion layer.

This module is **additive**: it imports the existing ``Task`` / ``sim_call``
plumbing from ``selfplay.tasks`` and exposes ``LOCOMOTION_TASKS`` plus an
``extend_task_bank()`` helper.

The live ``robotics_selfplay.py`` is not modified by this file. To run a
self-play loop that includes these tasks, call ``extend_task_bank()`` once
at startup, or simply concatenate the lists yourself.

Each task here:
  - tells Hermes to call ``tron1_walk_command`` (not raw ``tron1_velocity``)
  - grades on a measurable physical quantity (distance moved, stop margin,
    yaw error)
  - uses randomized reset poses where reasonable, so the agent can't
    memorize a trajectory

LimX-style influences:
  - reward shaping separated from success criterion (so a partial-credit
    grader can still emit a non-zero reward without flipping success)
  - safety penalties (e.g. unsafe high-velocity command) are explicit
"""

from __future__ import annotations

import math
import random
import re
from typing import Any, Dict, List, Tuple

from . import tasks as _live  # selfplay.tasks
from .tasks import Task, sim_call


# ---------------------------------------------------------------------------
# Helpers — shared between graders
# ---------------------------------------------------------------------------

def _pose(sim: Dict[str, Any]) -> Dict[str, float]:
    return sim.get("pose") or {}


def _dist(a: Dict[str, float], b: Tuple[float, float]) -> float:
    return math.hypot(a.get("x", 0.0) - b[0], a.get("y", 0.0) - b[1])


def _wrap_pi(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def _initial_pose() -> Dict[str, float]:
    """Pose snapshot taken at episode start. Cached in sim under the key
    'initial_pose' by the sim's reset op (if implemented); otherwise this
    returns the current pose at evaluation time, which makes some graders
    less informative but never crashes."""
    r = sim_call("get_initial_pose")
    if r.get("ok"):
        return r.get("data") or {}
    r2 = sim_call("get_pose")
    return r2.get("data") or {}


def _unsafe_command_penalty(transcript: str) -> float:
    """Penalize obviously unsafe velocity choices in the transcript.

    A walking biped should not be told to move at 5 m/s. If the LLM
    requests something outrageous we deduct reward even if the clipper
    saved us in practice.
    """
    penalty = 0.0
    for m in re.finditer(r'"vx"\s*:\s*(-?\d+(?:\.\d+)?)', transcript):
        try:
            v = float(m.group(1))
            if abs(v) > 1.5:
                penalty += 0.05
        except ValueError:
            continue
    for m in re.finditer(r'"yaw_rate"\s*:\s*(-?\d+(?:\.\d+)?)', transcript):
        try:
            v = float(m.group(1))
            if abs(v) > 1.5:
                penalty += 0.05
        except ValueError:
            continue
    return min(0.5, penalty)


# ---------------------------------------------------------------------------
# Graders
# ---------------------------------------------------------------------------

def _grade_walk_forward_1m(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    end = _pose(sim)
    start = sim.get("initial_pose") or _initial_pose()
    dx = end.get("x", 0.0) - (start.get("x", 0.0) if start else 0.0)
    dy = end.get("y", 0.0) - (start.get("y", 0.0) if start else 0.0)
    moved = math.hypot(dx, dy)
    penalty = _unsafe_command_penalty(transcript)
    if 0.85 <= moved <= 1.25:
        return True, max(0.3, 1.0 - abs(moved - 1.0)) - penalty, f"moved {moved:.2f} m"
    if 0.6 <= moved < 0.85:
        return True, 0.4 - penalty, f"short: {moved:.2f} m"
    if moved > 1.5:
        return False, -0.2 - penalty, f"overshoot: {moved:.2f} m"
    return False, -0.2 - penalty, f"didn't move enough: {moved:.2f} m"


def _grade_turn_to_heading(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Robot starts at yaw=0, should turn to yaw≈π/2 (90° left)."""
    end = _pose(sim)
    err = abs(_wrap_pi(end.get("yaw", 0.0) - math.pi / 2))
    if err < math.radians(10):
        return True, 1.0 - err, f"yaw err {math.degrees(err):.1f}°"
    if err < math.radians(25):
        return True, 0.4, f"close yaw err {math.degrees(err):.1f}°"
    return False, -0.1, f"yaw off by {math.degrees(err):.0f}°"


def _grade_approach_wall_gauge(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Stop within 0.9–1.4 m of the north-wall gauge (preserves dial in frame)."""
    end = _pose(sim)
    # Target stand-off point: 1.2 m south of the gauge at (0, 5.85)
    d = _dist(end, (0.0, 4.65))
    if 0.9 <= d <= 1.4:
        return True, 1.0 - abs(d - 1.15), f"stand-off {d:.2f} m"
    if d < 0.6:
        return False, -0.2, f"too close: {d:.2f} m (dial clipped)"
    if d <= 2.0:
        return True, 0.3, f"approx OK: {d:.2f} m"
    return False, -0.1, f"too far: {d:.2f} m"


def _grade_stop_at_viewing_distance(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Robot should stop ~1.0 m short of (5, 3) — door viewing position."""
    end = _pose(sim)
    d = _dist(end, (5.0, 3.0))
    if 0.8 <= d <= 1.4:
        return True, 1.0 - abs(d - 1.0), f"stand-off {d:.2f} m"
    if d < 0.5:
        return False, -0.3, f"hit-the-wall close: {d:.2f} m"
    return False, -0.1, f"off target: {d:.2f} m"


def _grade_navigate_around_obstacle(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Move 2 m forward without ending inside any obstacle bbox."""
    end = _pose(sim)
    start = sim.get("initial_pose") or _initial_pose()
    moved = math.hypot(
        end.get("x", 0.0) - (start.get("x", 0.0) if start else 0.0),
        end.get("y", 0.0) - (start.get("y", 0.0) if start else 0.0),
    )
    obstacles = sim.get("obstacles") or []
    min_clearance = min(
        (math.hypot(end.get("x", 0.0) - o.get("x", 99),
                    end.get("y", 0.0) - o.get("y", 99))
         for o in obstacles),
        default=99.0,
    )
    if moved >= 1.5 and min_clearance > 0.4:
        return True, max(0.3, 1.0 - abs(moved - 2.0) - max(0.0, 0.6 - min_clearance)), (
            f"moved {moved:.2f} m, clearance {min_clearance:.2f} m"
        )
    if min_clearance <= 0.3:
        return False, -0.3, f"collided/very close (clearance {min_clearance:.2f} m)"
    return False, -0.1, f"moved {moved:.2f} m, clearance {min_clearance:.2f} m"


def _grade_return_home_with_locomotion(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Must use tron1_walk_command (not raw tron1_velocity) to return home."""
    used_walk = "tron1_walk_command" in transcript
    end = _pose(sim)
    d = _dist(end, (0.0, -4.0))
    if used_walk and d < 0.6:
        return True, 1.0 - d, f"walk_command used, home dist {d:.2f} m"
    if used_walk and d < 1.5:
        return True, 0.4, f"walk_command used, close: {d:.2f} m"
    if not used_walk and d < 0.6:
        return True, 0.5, "home reached but via raw velocity tool"
    return False, -0.1, f"d={d:.2f}, used_walk={used_walk}"


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

LOCOMOTION_TASKS: List[Task] = [
    Task(
        id="walk-forward-1m",
        prompt=(
            "Use tron1_walk_command (NOT tron1_velocity) to drive forward "
            "about 1.0 m. Issue SHORT bursts (e.g. vx=0.4, duration=1.0) "
            "and call tron1_get_pose between bursts to check progress. "
            "Stop within 0.85–1.25 m of your starting x/y. Report the "
            "final pose."
        ),
        budget_s=120,
        weight=1.0,
        grade=_grade_walk_forward_1m,
        reset_to=(0.0, -4.0, 0.0),  # facing east
    ),
    Task(
        id="turn-to-heading",
        prompt=(
            "Using tron1_walk_command with vx=0 and a positive yaw_rate, "
            "turn the robot until its yaw is approximately π/2 (90° to the "
            "left). Re-read tron1_get_pose between bursts. Stop when "
            "|yaw - π/2| < 10°. Report final yaw in radians."
        ),
        budget_s=90,
        weight=1.0,
        grade=_grade_turn_to_heading,
        reset_to=(0.0, -4.0, 0.0),
    ),
    Task(
        id="approach-wall-gauge",
        prompt=(
            "Drive to the NORTH wall gauge at (0, 5.85) using "
            "tron1_walk_command. Stop at a viewing distance of 1.0–1.3 m "
            "so the full circular dial is visible (do NOT drive into the "
            "wall). Read the skill 'approach-distance' before planning. "
            "Report final pose."
        ),
        budget_s=200,
        weight=1.2,
        grade=_grade_approach_wall_gauge,
        reset_to=(0.0, -4.0, math.pi / 2),
    ),
    Task(
        id="stop-at-viewing-distance",
        prompt=(
            "Drive toward the east door at (5.0, 3.0). Stop ~1.0 m "
            "short — i.e. final position about (4.0, 3.0). Use "
            "tron1_walk_command in short bursts. Read pose between "
            "bursts. Report final pose."
        ),
        budget_s=200,
        weight=1.0,
        grade=_grade_stop_at_viewing_distance,
        reset_to=(0.0, -4.0, math.pi / 2),
    ),
    Task(
        id="navigate-around-obstacle",
        prompt=(
            "Move approximately 2.0 m forward from your starting position. "
            "There are obstacles between you and the goal — use "
            "tron1_walk_command (with non-zero yaw_rate when needed) to "
            "steer around them. Keep at least 0.4 m clearance from any "
            "obstacle. Use tron1_get_image to check what's in front "
            "before committing. Report final pose."
        ),
        budget_s=240,
        weight=1.2,
        grade=_grade_navigate_around_obstacle,
        reset_to=(0.0, -4.0, math.pi / 2),
    ),
    Task(
        id="return-home-with-locomotion",
        prompt=(
            "You are somewhere in the room. Use tron1_walk_command "
            "(NOT raw tron1_velocity) to return to the HOME zone at "
            "(0, -4). Stop within 0.6 m. After every command call "
            "tron1_get_pose to confirm you actually moved. Report final "
            "pose."
        ),
        budget_s=200,
        weight=1.0,
        grade=_grade_return_home_with_locomotion,
        # Randomized start so the agent can't memorize a recipe.
        reset_to=None,
    ),
]


def extend_task_bank(target_list: List[Task] | None = None) -> List[Task]:
    """Append LOCOMOTION_TASKS to the live task bank.

    If ``target_list`` is omitted, mutates ``selfplay.tasks.TASKS``.
    """
    bank = target_list if target_list is not None else _live.TASKS
    existing_ids = {t.id for t in bank}
    for t in LOCOMOTION_TASKS:
        if t.id not in existing_ids:
            bank.append(t)
    return bank


def randomized_reset_pose(rng: random.Random | None = None) -> Tuple[float, float, float]:
    """Domain-randomized reset pose for tasks marked ``reset_to=None``.

    LimX-style DR placeholder. We don't randomize friction or mass here
    because the kinematic MuJoCo backend ignores them — those knobs will
    matter once a real RL policy is loaded.
    """
    r = rng or random.Random()
    x = r.uniform(-3.0, 3.0)
    y = r.uniform(-3.0, 3.0)
    yaw = r.uniform(-math.pi, math.pi)
    return x, y, yaw
