"""Task bank for Hermes-driven Tron 1 self-play.

Each Task owns its own prompt (given to Hermes), max turn budget, and a
`grade(transcript, sim)` function that queries the live sim for ground truth
and returns (success: bool, reward: float, reason: str).
"""

from __future__ import annotations

import json
import math
import re
import socket
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Sim client — query ground truth over the same TCP protocol Hermes uses
# ---------------------------------------------------------------------------

def sim_call(op: str, host: str = "127.0.0.1", port: int = 5556,
             timeout: float = 5.0, **fields: Any) -> Dict[str, Any]:
    payload = {"op": op, **fields}
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall((json.dumps(payload) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
            return json.loads(buf.decode()) if buf else {"ok": False, "error": "empty"}
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _first_number(text: str) -> float | None:
    m = _NUM_RE.search(text)
    return float(m.group(0)) if m else None


def _extract_values_json(text: str) -> List[Dict[str, Any]]:
    """Scan transcript for JSON objects that look like gauge readings."""
    out = []
    for m in re.finditer(r"\{[^{}]*\"value\"\s*:\s*(-?\d+(?:\.\d+)?)[^{}]*\}", text):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and "value" in obj:
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------

@dataclass
class Task:
    id: str
    prompt: str
    weight: float = 1.0
    budget_s: int = 180
    grade: Callable[[str, Dict[str, Any]], Tuple[bool, float, str]] = field(
        default=lambda t, s: (True, 0.0, "no grader")
    )
    reset_to: Tuple[float, float, float] | None = None  # (x, y, yaw_rad)


# ----- Grader implementations -----

def _grade_read_gauge_N(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    truth = sim.get("gauge_N", {})
    if not truth:
        return False, -0.1, "no gauge N truth"
    objs = _extract_values_json(transcript)
    if not objs:
        return False, -0.3, "no JSON reading in transcript"
    pred = objs[-1]  # last reading is usually the final answer
    try:
        pv = float(pred["value"])
        tv = float(truth["value"])
        rng = truth["max"] - truth["min"]
        err_pct = abs(pv - tv) / rng * 100
    except (KeyError, ValueError, ZeroDivisionError) as e:
        return False, -0.3, f"parse error: {e}"
    units_ok = pred.get("units", "").strip().lower() == truth["units"].strip().lower()
    if err_pct < 8.0 and units_ok:
        return True, 1.0 - err_pct / 20.0, f"err {err_pct:.1f}% on {truth['units']}"
    if err_pct < 15.0 and units_ok:
        return True, 0.3, f"marginal err {err_pct:.1f}%"
    return False, -0.2, f"err {err_pct:.1f}%, units_ok={units_ok}"


def _grade_read_any_gauge(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Accept a reading of any of the 3 gauges."""
    all_g = sim.get("all_gauges", {})
    if not all_g:
        return False, -0.1, "no gauges truth"
    objs = _extract_values_json(transcript)
    if not objs:
        return False, -0.3, "no JSON reading"
    pred = objs[-1]
    try:
        pv = float(pred["value"])
        punits = pred.get("units", "").strip()
    except (KeyError, ValueError) as e:
        return False, -0.3, f"parse: {e}"
    # find the best matching gauge
    best = None
    for wall, t in all_g.items():
        if punits.lower() != t["units"].strip().lower():
            continue
        err_pct = abs(pv - float(t["value"])) / (t["max"] - t["min"]) * 100
        if best is None or err_pct < best[1]:
            best = (wall, err_pct)
    if best is None:
        return False, -0.2, f"no gauge matches units '{punits}'"
    wall, err_pct = best
    if err_pct < 10:
        return True, max(0.2, 1.0 - err_pct / 15.0), f"{wall} err {err_pct:.1f}%"
    return False, -0.1, f"{wall} err {err_pct:.1f}% (too high)"


def _grade_navigate_home(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Did the robot end up within 0.5 m of the home zone (0, -4)?"""
    pose = sim.get("pose", {})
    if not pose:
        return False, -0.1, "no pose"
    dist = math.hypot(pose.get("x", 99) - 0.0, pose.get("y", 99) - (-4.0))
    if dist < 0.5:
        return True, 1.0 - dist / 1.0, f"home dist {dist:.2f}m"
    if dist < 1.5:
        return True, 0.3, f"close: {dist:.2f}m"
    return False, -0.1, f"far from home: {dist:.2f}m"


def _grade_by_distance(sim: Dict[str, Any],
                       target: Tuple[float, float],
                       tol: float = 0.5,
                       tol_ok: float = 1.0) -> Tuple[bool, float, str]:
    """Generic distance grader used by simple navigation tasks."""
    pose = sim.get("pose", {})
    if not pose: return False, -0.1, "no pose"
    d = math.hypot(pose.get("x", 99) - target[0], pose.get("y", 99) - target[1])
    if d < tol:
        return True, max(0.3, 1.0 - d / (tol * 2)), f"within {d:.2f} m"
    if d < tol_ok:
        return True, 0.2, f"marginally close: {d:.2f} m"
    return False, -0.1, f"far: {d:.2f} m"


def _grade_find_door(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Robot should be within 1.5 m of the door at (5.88, 3.0), facing east."""
    pose = sim.get("pose", {})
    if not pose:
        return False, -0.1, "no pose"
    dx = 5.88 - pose.get("x", 0)
    dy = 3.0 - pose.get("y", 0)
    dist = math.hypot(dx, dy)
    bearing_to_door = math.atan2(dy, dx) - pose.get("yaw", 0)
    bearing_to_door = (bearing_to_door + math.pi) % (2 * math.pi) - math.pi
    if dist < 1.5 and abs(bearing_to_door) < 0.6:
        return True, max(0.3, 1.0 - dist / 2.0), f"door dist {dist:.2f}m bearing {math.degrees(bearing_to_door):+.0f}°"
    if dist < 2.5:
        return True, 0.2, f"close: {dist:.2f}m"
    return False, -0.1, f"far: {dist:.2f}m"


def _grade_count_obstacles(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Agent should report the count of obstacles (4 total: 3 boxes + 1 cone)."""
    # find standalone integer 1-10 in the last 400 chars
    tail = transcript[-400:]
    nums = re.findall(r"\b([1-9])\b", tail)
    if not nums:
        return False, -0.3, "no count reported"
    pred = int(nums[-1])
    truth_count = 4
    if pred == truth_count:
        return True, 1.0, f"correct count = {pred}"
    if abs(pred - truth_count) == 1:
        return True, 0.3, f"pred {pred} vs {truth_count} (close)"
    return False, -0.2, f"pred {pred} vs {truth_count}"


def _grade_describe_scene(transcript: str, sim: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Scene description should mention >=3 of: gauge, door, box/obstacle, floor, wall, zone."""
    low = transcript.lower()
    keywords = ["gauge", "dial", "meter", "door", "box", "obstacle",
                "floor", "wall", "zone", "marker", "checker"]
    hits = sum(1 for k in keywords if k in low)
    if hits >= 4:
        return True, 0.8, f"{hits} scene keywords matched"
    if hits >= 2:
        return True, 0.3, f"only {hits} keywords"
    return False, -0.1, f"{hits} keywords — description too thin"


# ----- Task bank -----

TASKS: List[Task] = [
    Task(
        id="read-gauge-N",
        prompt=("Use the read-wall-gauge skill to read the gauge on the "
                "NORTH wall (at world y=+5.85). Drive to y≈4.65, capture "
                "with tron1_get_image, and read with qwen_vl_local. "
                "IMPORTANT: your final message MUST contain a JSON object "
                "on its own line formatted exactly as "
                "{\"value\": <float>, \"units\": \"<str>\"}."),
        budget_s=200, weight=2.0, grade=_grade_read_gauge_N,
        reset_to=(0.0, -4.0, math.pi / 2),
    ),
    Task(
        id="read-any-gauge",
        prompt=("There are 3 analog gauges in this room — NORTH at (0,5.85), "
                "EAST at (5.85,-1.5), WEST at (-5.85,2.0). Drive to any one "
                "of them and read it. Report JSON "
                "{\"value\": <float>, \"units\": \"<str>\"}."),
        budget_s=180, weight=1.5, grade=_grade_read_any_gauge,
        reset_to=(0.0, -4.0, math.pi / 2),
    ),
    Task(
        id="navigate-home",
        prompt=("Use tron1_velocity (and tron1_get_pose to check progress) "
                "to return to the HOME zone — the green circular floor "
                "marker at world (0, -4). Stop within 0.5 m. Report the "
                "final pose."),
        budget_s=120, weight=1.0, grade=_grade_navigate_home,
        reset_to=(2.5, 2.5, 0.3),
    ),
    Task(
        id="find-door",
        prompt=("Follow the navigate-to-landmark skill. Target: door at "
                "world (5.0, 3.0), facing east (yaw ≈ 0). "
                "Current pose is (0, -4, yaw=π/2). "
                "Read the skill's 'Failure notes' before planning — use as "
                "many velocity bursts as needed (typically 6–10). "
                "Report final pose as your last message."),
        budget_s=300, weight=1.0, grade=_grade_find_door,
        reset_to=(0.0, -4.0, math.pi / 2),
    ),
    Task(
        id="navigate-to-charge",
        prompt=("Follow the navigate-to-landmark skill. Target: charge "
                "zone at world (-4.5, -4.0). Current pose is approximately "
                "(2.5, 2.5, yaw=0.3). "
                "Read the skill's 'Failure notes' before planning — use "
                "short (~1 s) bursts, re-read pose between each, budget "
                "8–10 calls. Stop within 0.5 m. Report final pose."),
        budget_s=300, weight=1.0, grade=lambda t, s:
            _grade_by_distance(s, (-4.5, -4.0), tol=0.5, tol_ok=1.0),
        reset_to=(2.5, 2.5, 0.3),
    ),
    Task(
        id="count-obstacles",
        prompt=("Look around the room (rotate in place with tron1_velocity "
                "angular or take multiple photos from different yaws) and "
                "count the obstacle boxes/cones scattered on the floor. "
                "Answer: how many obstacles are there? Reply with a single "
                "integer after your reasoning."),
        budget_s=180, weight=1.0, grade=_grade_count_obstacles,
        reset_to=(0.0, -4.0, math.pi / 2),
    ),
    Task(
        id="describe-scene",
        prompt=("Capture the ego-camera frame and produce a structured "
                "description of what the robot sees. Use the describe-scene "
                "skill. Mention any gauges, doors, obstacles, floor markers, "
                "or walls visible."),
        budget_s=90, weight=0.8, grade=_grade_describe_scene,
        reset_to=(0.0, -4.0, math.pi / 2),
    ),
]


# ---------------------------------------------------------------------------
# Resetting the sim between episodes
# ---------------------------------------------------------------------------

def reset_robot(pose: Tuple[float, float, float] | None = None,
                regen_gauges: bool = True) -> None:
    """Reset the sim to the given pose (x, y, yaw_rad), or default. When
    regen_gauges is True, randomize the gauge textures so each episode
    sees a different reading (avoids the agent cheating on stale state)."""
    if pose is None:
        sim_call("reset", regen_gauges=regen_gauges)
    else:
        x, y, yaw = pose
        sim_call("reset", x=x, y=y, yaw=yaw, regen_gauges=regen_gauges)


def gather_sim_truth() -> Dict[str, Any]:
    """Snapshot ground truth for the grader at end of episode."""
    out = {}
    r = sim_call("all_gauges_truth")
    if r.get("ok"):
        out["all_gauges"] = r["data"]
        out["gauge_N"] = r["data"].get("N", {})
    r = sim_call("get_pose")
    if r.get("ok"):
        out["pose"] = r["data"]
    return out
