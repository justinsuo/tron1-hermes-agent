"""High-level locomotion tool for Hermes.

Exposes ``tron1_walk_command(vx, vy, yaw_rate, duration)``. Hermes uses this
to express *intent* (move forward at 0.3 m/s for 2 s) without ever touching
joint torques.

Pipeline per call:

  1. Coerce + validate inputs.
  2. Clip against ``SafetyLimits`` via ``CommandAdapter``.
  3. Read current pose from the sim sidecar (start_pose).
  4. Build an observation, call the policy runner (Fake today), and
     forward the resulting velocity setpoint to ``tron1_velocity``.
  5. Read end_pose and log to ``~/.tron1-locomotion-log.jsonl``.
  6. Return a structured result.

If anything in the chain fails — sidecar unreachable, policy throws,
sim returns no pose — we still return a JSON object with ``ok=false`` and
a human-readable error. Hermes is allowed to retry.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Make the repo's locomotion/ package importable. Hermes auto-discovers
# tools from ~/.hermes/hermes-agent/tools/, but our locomotion package
# lives in the tron1-hermes-agent repo. This shim adds the repo root to
# sys.path lazily — failures are non-fatal so the tool still loads.
def _ensure_locomotion_importable() -> None:
    if "locomotion" in sys.modules:
        return
    candidates = [
        os.environ.get("TRON1_HERMES_AGENT_REPO"),
        os.path.expanduser("~/tron1-hermes-agent"),
        "/Users/justinsuo/tron1-hermes-agent",
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(c)
        if (p / "locomotion" / "__init__.py").exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
            return


_ensure_locomotion_importable()

try:
    from locomotion import (  # type: ignore[import-not-found]
        CommandAdapter,
        FakePolicyRunner,
        LocomotionLogger,
        ObservationBuilder,
        ObservationSpec,
        PolicyLoadError,
        SafetyLimits,
    )
    _LOCOMOTION_OK = True
    _LOCOMOTION_ERR: Optional[str] = None
except Exception as e:  # noqa: BLE001 — tool must still register if pkg missing
    _LOCOMOTION_OK = False
    _LOCOMOTION_ERR = f"locomotion package unavailable: {e}"


# ---------------------------------------------------------------------------
# Sidecar helpers — same protocol as tron1_ros2_tool.py
# ---------------------------------------------------------------------------

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 5556
_DEFAULT_TIMEOUT = 15.0


def _sidecar_config() -> tuple[str, int, float]:
    return (
        os.getenv("HERMES_ROS2_HOST", _DEFAULT_HOST),
        int(os.getenv("HERMES_ROS2_PORT", str(_DEFAULT_PORT))),
        float(os.getenv("HERMES_ROS2_TIMEOUT", str(_DEFAULT_TIMEOUT))),
    )


def _sidecar_call(request: Dict[str, Any]) -> Dict[str, Any]:
    host, port, timeout = _sidecar_config()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
            if not buf:
                return {"ok": False, "error": "empty sidecar response"}
            return json.loads(buf.decode("utf-8").strip())
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        return {"ok": False, "error": f"sidecar unreachable: {type(e).__name__}: {e}"}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"bad sidecar json: {e}"}


def _sidecar_pose() -> Optional[Dict[str, float]]:
    r = _sidecar_call({"op": "get_pose"})
    if not r.get("ok"):
        return None
    d = r.get("data") or {}
    return {
        "x": float(d.get("x", 0.0)),
        "y": float(d.get("y", 0.0)),
        "z": float(d.get("z", 0.0)),
        "yaw": float(d.get("yaw", 0.0)),
    }


def _sidecar_velocity(linear: float, angular: float, duration: float) -> Dict[str, Any]:
    return _sidecar_call({
        "op": "publish_cmd_vel",
        "linear": float(linear),
        "angular": float(angular),
        "duration": float(duration),
    })


def _check_sidecar_reachable() -> bool:
    host, port, _ = _sidecar_config()
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Lazy singletons — built on first call so import is cheap
# ---------------------------------------------------------------------------

_adapter: Optional["CommandAdapter"] = None  # type: ignore[name-defined]
_runner: Optional[Any] = None
_obs_builder: Optional["ObservationBuilder"] = None  # type: ignore[name-defined]
_logger_obj: Optional["LocomotionLogger"] = None  # type: ignore[name-defined]


def _ensure_locomotion() -> Optional[str]:
    """Construct the locomotion singletons. Returns an error string or None."""
    if not _LOCOMOTION_OK:
        return _LOCOMOTION_ERR or "locomotion package missing"
    global _adapter, _runner, _obs_builder, _logger_obj
    if _adapter is None:
        _adapter = CommandAdapter(limits=SafetyLimits())
    if _runner is None:
        # TODO: switch to PolicyRunner once a trained .pt is available.
        # The env var below lets ops override without code changes.
        checkpoint = os.getenv("TRON1_POLICY_CHECKPOINT")
        if checkpoint:
            try:
                from locomotion import PolicyRunner  # type: ignore[import-not-found]
                _runner = PolicyRunner(checkpoint)
            except PolicyLoadError as e:
                logger.warning("policy load failed (%s) — falling back to fake", e)
                _runner = FakePolicyRunner()
        else:
            _runner = FakePolicyRunner()
    if _obs_builder is None:
        _obs_builder = ObservationBuilder(spec=ObservationSpec())
    if _logger_obj is None:
        _logger_obj = LocomotionLogger()
    return None


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def _handle_walk_command(args: Dict[str, Any], **_: Any) -> str:
    err = _ensure_locomotion()
    if err:
        return json.dumps({"ok": False, "error": err})

    try:
        cmd = _adapter.build(  # type: ignore[union-attr]
            vx=args.get("vx", 0.0),
            vy=args.get("vy", 0.0),
            yaw_rate=args.get("yaw_rate", 0.0),
            duration=args.get("duration", 1.0),
        )
    except ValueError as e:
        return json.dumps({"ok": False, "error": f"invalid command: {e}"})

    start_pose = _sidecar_pose()
    log_record = _logger_obj.begin(  # type: ignore[union-attr]
        command={
            "vx": float(args.get("vx", 0.0)),
            "vy": float(args.get("vy", 0.0)),
            "yaw_rate": float(args.get("yaw_rate", 0.0)),
            "duration": float(args.get("duration", 1.0)),
        },
        clipped_command=cmd.to_dict(),
        start_pose=start_pose,
    )

    # Build the policy observation — the kinematic backend doesn't use the
    # resulting action today, but doing this every call keeps the shape
    # contract honest so a real policy is a drop-in replacement.
    obs = _obs_builder.build(  # type: ignore[union-attr]
        base_ang_vel=(0.0, 0.0, 0.0),  # TODO surface ang_vel from sidecar
        base_quat=(1.0, 0.0, 0.0, 0.0),  # TODO surface quat
        joint_pos=[0.0] * _obs_builder.spec.num_joints,  # type: ignore[union-attr]
        joint_vel=[0.0] * _obs_builder.spec.num_joints,  # type: ignore[union-attr]
        last_action=[0.0] * _obs_builder.spec.num_joints,  # type: ignore[union-attr]
        command=cmd.as_policy_command(),
    )
    try:
        _ = _runner.act(obs, cmd.as_policy_command())  # type: ignore[union-attr]
        runner_kind = _runner.get_metadata().get("name", "?")  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        runner_kind = "FAILED"
        _logger_obj.end(log_record, end_pose=start_pose, success=False,  # type: ignore[union-attr]
                        error=f"policy.act failed: {e}")
        return json.dumps({"ok": False, "error": f"policy: {e}",
                           "command": cmd.to_dict()})

    setpoint = cmd.as_velocity_setpoint()
    sidecar_resp = _sidecar_velocity(**setpoint)
    if not sidecar_resp.get("ok"):
        _logger_obj.end(log_record, end_pose=start_pose, success=False,  # type: ignore[union-attr]
                        error=sidecar_resp.get("error", "sidecar error"))
        return json.dumps({
            "ok": False,
            "error": sidecar_resp.get("error", "sidecar error"),
            "command": cmd.to_dict(),
        })

    end_pose = _sidecar_pose()
    notes = list(cmd.clip_notes) + [f"runner={runner_kind}"]
    final_record = _logger_obj.end(  # type: ignore[union-attr]
        log_record, end_pose=end_pose, success=True, notes=notes,
    )

    return json.dumps({
        "ok": True,
        "command": cmd.to_dict(),
        "start_pose": start_pose,
        "end_pose": end_pose,
        "distance_moved": final_record.get("estimated_distance"),
        "yaw_change": final_record.get("yaw_change"),
        "fell": final_record.get("fell", False),
        "collided": final_record.get("collided", False),
        "notes": notes,
        "runner": runner_kind,
    }, default=str)


# ---------------------------------------------------------------------------
# Schema + registration
# ---------------------------------------------------------------------------

TRON1_WALK_COMMAND_SCHEMA = {
    "name": "tron1_walk_command",
    "description": (
        "Issue a high-level locomotion command. The command is clipped to "
        "safe limits (vx ≤ 0.8 m/s, vy ≤ 0.4 m/s, yaw_rate ≤ 0.8 rad/s, "
        "duration ≤ 2 s), routed through a locomotion policy (fake by "
        "default; loads a trained .pt if TRON1_POLICY_CHECKPOINT is set), "
        "executed via the existing sim backend, and logged to "
        "~/.tron1-locomotion-log.jsonl. Returns start/end pose, distance "
        "moved, and a 'fell' / 'collided' flag for failure detection. "
        "Prefer SHORT bursts and re-read pose between calls."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "vx": {"type": "number",
                   "description": "Forward velocity in body frame, m/s. Default 0."},
            "vy": {"type": "number",
                   "description": "Lateral velocity in body frame, m/s. Default 0."},
            "yaw_rate": {"type": "number",
                         "description": "Yaw rate, rad/s. Default 0."},
            "duration": {"type": "number",
                         "description": "How long to apply the command, seconds. Default 1.0."},
        },
        "required": [],
    },
}


# Hermes' registry uses AST inspection on top-level register() calls, so we
# import + register at module scope. If the registry import fails the tool
# simply won't show up — that's the right behavior in non-hermes contexts
# (tests, scripts).
try:
    from tools.registry import registry  # type: ignore[import-not-found]

    registry.register(
        name="tron1_walk_command",
        toolset="tron1",
        schema=TRON1_WALK_COMMAND_SCHEMA,
        handler=_handle_walk_command,
        check_fn=_check_sidecar_reachable,
        emoji="🦵",
    )
except ImportError:
    # Not running inside Hermes — fine for tests.
    pass
