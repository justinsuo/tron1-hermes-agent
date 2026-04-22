"""Tron 1 ROS 2 bridge tool for Hermes Agent.

Exposes six LLM-callable tools that talk to the LimX Tron 1 robot (real or sim)
over the ROS 2 DDS graph.  Since Hermes runs on macOS (no ROS 2) and the robot
stack runs on Ubuntu + ROS 2 Humble, these tools speak a tiny JSON protocol to
the companion ``sidecar.py`` process that sits inside the ROS 2 environment.

Environment variables:
    HERMES_ROS2_HOST    Host running the sidecar (default: 127.0.0.1)
    HERMES_ROS2_PORT    Sidecar TCP port (default: 5556)
    HERMES_ROS2_TIMEOUT Seconds to wait for a response (default: 5)

Sidecar code: ~/ros2_sidecar/sidecar.py
Deploy:       ~/ros2_sidecar/deploy_to_vm.sh
"""

import json
import logging
import os
import socket
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 5556
_DEFAULT_TIMEOUT = 15.0  # generous so first get_image call (renderer warmup) doesn't time out

_lock = threading.Lock()


def _config() -> tuple[str, int, float]:
    return (
        os.getenv("HERMES_ROS2_HOST", _DEFAULT_HOST),
        int(os.getenv("HERMES_ROS2_PORT", str(_DEFAULT_PORT))),
        float(os.getenv("HERMES_ROS2_TIMEOUT", str(_DEFAULT_TIMEOUT))),
    )


def _call(request: Dict[str, Any]) -> Dict[str, Any]:
    """Send one JSON request to the sidecar; return the decoded response.

    Opens a fresh TCP connection per call. Cheap enough (<1ms locally) and
    trivially robust to sidecar restarts.
    """
    host, port, timeout = _config()
    with _lock:
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                payload = (json.dumps(request) + "\n").encode("utf-8")
                sock.sendall(payload)
                # Read one line of response
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                if not buf:
                    return {"ok": False, "error": "empty response from sidecar"}
                return json.loads(buf.decode("utf-8").strip())
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            return {
                "ok": False,
                "error": (
                    f"sidecar unreachable at {host}:{port} ({type(e).__name__}: {e}). "
                    "Start the VM, run ~/ros2_sidecar/deploy_to_vm.sh, "
                    "and port-forward: "
                    f"ssh -N -L {port}:localhost:{port} -p 2222 justin@localhost"
                ),
            }
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"bad response json: {e}"}


def _ok_json(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, default=str)


def _err_json(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


def _unwrap(resp: Dict[str, Any]) -> str:
    """Turn a sidecar response into a JSON string for the model."""
    if resp.get("ok"):
        return _ok_json(resp.get("data"))
    return _err_json(resp.get("error", "unknown error"))


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def _handle_ping(args: Dict[str, Any], **_: Any) -> str:
    return _unwrap(_call({"op": "ping"}))


def _handle_send_command(args: Dict[str, Any], **_: Any) -> str:
    text = (args.get("text") or "").strip()
    if not text:
        return _err_json("text is required")
    return _unwrap(_call({"op": "publish_command", "text": text}))


def _handle_velocity(args: Dict[str, Any], **_: Any) -> str:
    try:
        linear = float(args.get("linear", 0.0))
        angular = float(args.get("angular", 0.0))
        duration = float(args.get("duration", 1.0))
    except (TypeError, ValueError) as e:
        return _err_json(f"invalid numeric arg: {e}")
    # Safety caps — Tron 1 is a ~20kg biped, don't let the LLM command crazy speeds.
    linear = max(-1.0, min(1.0, linear))
    angular = max(-2.0, min(2.0, angular))
    duration = max(0.0, min(10.0, duration))
    return _unwrap(_call({
        "op": "publish_cmd_vel",
        "linear": linear, "angular": angular, "duration": duration,
    }))


def _handle_goto(args: Dict[str, Any], **_: Any) -> str:
    try:
        x = float(args["x"])
        y = float(args["y"])
        yaw = float(args.get("yaw", 0.0))
    except (KeyError, TypeError, ValueError) as e:
        return _err_json(f"invalid pose arg: {e}")
    frame = args.get("frame", "map")
    return _unwrap(_call({
        "op": "publish_goal",
        "x": x, "y": y, "yaw": yaw, "frame": frame,
    }))


def _handle_get_scene(args: Dict[str, Any], **_: Any) -> str:
    return _unwrap(_call({"op": "get_scene"}))


def _handle_get_detections(args: Dict[str, Any], **_: Any) -> str:
    return _unwrap(_call({"op": "get_detections"}))


def _handle_get_pose(args: Dict[str, Any], **_: Any) -> str:
    return _unwrap(_call({"op": "get_pose"}))


def _handle_get_image(args: Dict[str, Any], **_: Any) -> str:
    """Return the latest camera frame as base64 JPEG.

    The LLM can pass this straight into qwen_vl_local or vision_analyze_tool.
    """
    resp = _call({"op": "get_image"})
    if not resp.get("ok"):
        return _err_json(resp.get("error", "no image"))
    # Persist to /tmp so the agent can reference it by path if it prefers files.
    data = resp.get("data") or {}
    b64 = data.get("jpeg_base64", "")
    ts = data.get("ts", 0)
    out = {"jpeg_base64": b64, "ts": ts}
    try:
        import base64 as _b64
        import tempfile
        path = tempfile.NamedTemporaryFile(
            prefix="tron1_image_", suffix=".jpg", delete=False
        ).name
        with open(path, "wb") as f:
            f.write(_b64.b64decode(b64))
        out["path"] = path
    except Exception:
        pass
    return _ok_json(out)


def _handle_list_topics(args: Dict[str, Any], **_: Any) -> str:
    return _unwrap(_call({"op": "list_topics"}))


def _check_sidecar_reachable() -> bool:
    host, port, _ = _config()
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

TRON1_PING_SCHEMA = {
    "name": "tron1_ping",
    "description": (
        "Check whether the Tron 1 ROS 2 sidecar is reachable. Returns a pong "
        "timestamp on success. Call this first before any other tron1_* tool "
        "if you're unsure whether the robot/sim stack is up."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

TRON1_SEND_COMMAND_SCHEMA = {
    "name": "tron1_send_command",
    "description": (
        "Publish a natural-language instruction to the /human_command topic. "
        "The on-robot LLM bridge (Qwen 3) picks it up and decides how to act. "
        "Use this for high-level intent like 'go to the kitchen' or "
        "'describe what you see'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Natural language command."},
        },
        "required": ["text"],
    },
}

TRON1_VELOCITY_SCHEMA = {
    "name": "tron1_velocity",
    "description": (
        "Send a timed /cmd_vel Twist. Use for small manual nudges or when "
        "navigation is inappropriate. Values are clamped to [-1, 1] m/s linear "
        "and [-2, 2] rad/s angular, duration capped at 10s. A zero Twist is "
        "published automatically when the duration ends."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "linear": {"type": "number", "description": "Forward velocity in m/s. Default 0."},
            "angular": {"type": "number", "description": "Yaw rate in rad/s. Default 0."},
            "duration": {"type": "number", "description": "Seconds to publish. Default 1."},
        },
        "required": [],
    },
}

TRON1_GOTO_SCHEMA = {
    "name": "tron1_goto",
    "description": (
        "Publish a PoseStamped to /goal_pose so Nav2 plans a path. Prefer this "
        "over tron1_velocity for anything beyond ~1m. Frame defaults to 'map'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "Target x in meters (frame)."},
            "y": {"type": "number", "description": "Target y in meters (frame)."},
            "yaw": {"type": "number", "description": "Target yaw in radians. Default 0."},
            "frame": {"type": "string", "description": "TF frame. Default 'map'."},
        },
        "required": ["x", "y"],
    },
}

TRON1_GET_SCENE_SCHEMA = {
    "name": "tron1_get_scene",
    "description": (
        "Return the latest /perception/scene_description string published by "
        "the on-robot perception node. This is a natural-language summary of "
        "what the robot currently sees."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

TRON1_GET_DETECTIONS_SCHEMA = {
    "name": "tron1_get_detections",
    "description": (
        "Return the latest /perception/detections JSON string (YOLO-style "
        "objects with bboxes and classes)."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

TRON1_GET_POSE_SCHEMA = {
    "name": "tron1_get_pose",
    "description": (
        "Return the latest odometry pose as {x, y, z, yaw} (yaw in radians)."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

TRON1_GET_IMAGE_SCHEMA = {
    "name": "tron1_get_image",
    "description": (
        "Grab the most recent RGB camera frame from /image_raw/compressed. "
        "Returns base64 JPEG plus a file path under /tmp. Pass the path or "
        "the bytes to qwen_vl_local or vision_analyze for interpretation."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

TRON1_LIST_TOPICS_SCHEMA = {
    "name": "tron1_list_topics",
    "description": "List all currently advertised ROS 2 topics as {name: type}.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

from tools.registry import registry

# Each registry.register(...) must be a top-level Expr statement — the registry
# discovers modules by AST-walking for that pattern (see registry.py's
# _is_registry_register_call). A for-loop wrapper is invisible to discovery.

registry.register(
    name="tron1_ping", toolset="tron1", schema=TRON1_PING_SCHEMA,
    handler=_handle_ping, check_fn=_check_sidecar_reachable, emoji="🤖",
)
registry.register(
    name="tron1_send_command", toolset="tron1", schema=TRON1_SEND_COMMAND_SCHEMA,
    handler=_handle_send_command, check_fn=_check_sidecar_reachable, emoji="🤖",
)
registry.register(
    name="tron1_velocity", toolset="tron1", schema=TRON1_VELOCITY_SCHEMA,
    handler=_handle_velocity, check_fn=_check_sidecar_reachable, emoji="🤖",
)
registry.register(
    name="tron1_goto", toolset="tron1", schema=TRON1_GOTO_SCHEMA,
    handler=_handle_goto, check_fn=_check_sidecar_reachable, emoji="🤖",
)
registry.register(
    name="tron1_get_scene", toolset="tron1", schema=TRON1_GET_SCENE_SCHEMA,
    handler=_handle_get_scene, check_fn=_check_sidecar_reachable, emoji="🤖",
)
registry.register(
    name="tron1_get_detections", toolset="tron1", schema=TRON1_GET_DETECTIONS_SCHEMA,
    handler=_handle_get_detections, check_fn=_check_sidecar_reachable, emoji="🤖",
)
registry.register(
    name="tron1_get_pose", toolset="tron1", schema=TRON1_GET_POSE_SCHEMA,
    handler=_handle_get_pose, check_fn=_check_sidecar_reachable, emoji="🤖",
)
registry.register(
    name="tron1_get_image", toolset="tron1", schema=TRON1_GET_IMAGE_SCHEMA,
    handler=_handle_get_image, check_fn=_check_sidecar_reachable, emoji="🤖",
)
registry.register(
    name="tron1_list_topics", toolset="tron1", schema=TRON1_LIST_TOPICS_SCHEMA,
    handler=_handle_list_topics, check_fn=_check_sidecar_reachable, emoji="🤖",
)
