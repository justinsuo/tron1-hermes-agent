#!/usr/bin/env python3
"""
ROS 2 Sidecar for Hermes Agent
------------------------------
Runs inside the tron1_ws environment (Ubuntu + ROS 2 Humble).
Bridges Hermes Agent (running on the Mac host, no ROS 2 installed)
to the ROS 2 DDS graph via a tiny TCP JSON protocol.

Start:
    source /opt/ros/humble/setup.bash
    source ~/tron1_ws/install/setup.bash
    python3 sidecar.py --host 0.0.0.0 --port 5556

Protocol (one JSON object per line, both directions):

Requests:
    {"op": "ping"}
    {"op": "publish_command", "text": "go to the kitchen"}
    {"op": "publish_cmd_vel", "linear": 0.5, "angular": 0.0, "duration": 2.0}
    {"op": "publish_goal", "x": 1.0, "y": 2.0, "yaw": 1.57, "frame": "map"}
    {"op": "get_scene"}
    {"op": "get_detections"}
    {"op": "get_pose"}
    {"op": "get_image", "topic": "/image_raw"}  # returns base64 JPEG
    {"op": "list_topics"}

Responses:
    {"ok": true, "data": ...}   on success
    {"ok": false, "error": "..."}   on failure

Security: binds to 0.0.0.0 by default for VM→host port-forward use.
Add --host 127.0.0.1 to restrict, or use an SSH tunnel.
"""

import argparse
import base64
import io
import json
import logging
import socket
import socketserver
import sys
import threading
import time
from typing import Any, Dict, Optional

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from std_msgs.msg import String
    from geometry_msgs.msg import PoseStamped, Twist
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import Image, CompressedImage
    ROS2_AVAILABLE = True
except ImportError as e:
    ROS2_AVAILABLE = False
    _IMPORT_ERROR = e

logger = logging.getLogger("hermes_ros2_sidecar")


class HermesBridge(Node):
    """ROS 2 node that holds the latest observation state for each topic of interest."""

    def __init__(self) -> None:
        super().__init__("hermes_bridge")

        # Latest observations (thread-safe via GIL, mutated only in ROS thread)
        self.latest_scene: Optional[str] = None
        self.latest_detections: Optional[str] = None
        self.latest_pose: Optional[Dict[str, float]] = None
        self.latest_image_bytes: Optional[bytes] = None
        self.latest_image_ts: float = 0.0

        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        qos_sensor = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # Publishers
        self.pub_command = self.create_publisher(String, "/human_command", qos_reliable)
        self.pub_cmd_vel = self.create_publisher(Twist, "/cmd_vel", qos_reliable)
        self.pub_goal = self.create_publisher(PoseStamped, "/goal_pose", qos_reliable)

        # Subscribers (latch the latest value)
        self.create_subscription(String, "/perception/scene_description",
                                 self._on_scene, qos_reliable)
        self.create_subscription(String, "/perception/detections",
                                 self._on_detections, qos_reliable)
        self.create_subscription(Odometry, "/odom", self._on_odom, qos_reliable)
        self.create_subscription(CompressedImage, "/image_raw/compressed",
                                 self._on_compressed_image, qos_sensor)

        self.get_logger().info("Hermes bridge node started.")

    # ----- subscription callbacks -----
    def _on_scene(self, msg: String) -> None:
        self.latest_scene = msg.data

    def _on_detections(self, msg: String) -> None:
        self.latest_detections = msg.data

    def _on_odom(self, msg: Odometry) -> None:
        p = msg.pose.pose.position
        o = msg.pose.pose.orientation
        # yaw from quaternion (ZYX convention, small-angle shortcut not used)
        import math
        siny_cosp = 2.0 * (o.w * o.z + o.x * o.y)
        cosy_cosp = 1.0 - 2.0 * (o.y * o.y + o.z * o.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        self.latest_pose = {"x": p.x, "y": p.y, "z": p.z, "yaw": yaw}

    def _on_compressed_image(self, msg: CompressedImage) -> None:
        # CompressedImage.data is already JPEG/PNG encoded bytes (format attr says which).
        self.latest_image_bytes = bytes(msg.data)
        self.latest_image_ts = time.time()

    # ----- request handlers -----
    def publish_command(self, text: str) -> None:
        m = String()
        m.data = text
        self.pub_command.publish(m)

    def publish_cmd_vel(self, linear: float, angular: float, duration: float = 1.0) -> None:
        end = time.time() + max(0.0, float(duration))
        rate_hz = 20.0
        period = 1.0 / rate_hz
        t = Twist()
        t.linear.x = float(linear)
        t.angular.z = float(angular)
        while time.time() < end:
            self.pub_cmd_vel.publish(t)
            time.sleep(period)
        # zero out when done
        self.pub_cmd_vel.publish(Twist())

    def publish_goal(self, x: float, y: float, yaw: float, frame: str = "map") -> None:
        import math
        ps = PoseStamped()
        ps.header.frame_id = frame
        ps.header.stamp = self.get_clock().now().to_msg()
        ps.pose.position.x = float(x)
        ps.pose.position.y = float(y)
        ps.pose.position.z = 0.0
        half = float(yaw) * 0.5
        ps.pose.orientation.z = math.sin(half)
        ps.pose.orientation.w = math.cos(half)
        self.pub_goal.publish(ps)

    def list_topics(self) -> Dict[str, str]:
        return {name: t[0] for name, t in self.get_topic_names_and_types()}


# ---------------------------------------------------------------------------
# TCP server
# ---------------------------------------------------------------------------

_BRIDGE: Optional[HermesBridge] = None
_EXECUTOR: Optional["SingleThreadedExecutor"] = None


def _handle_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch one JSON request. Runs on the socket thread."""
    if _BRIDGE is None:
        return {"ok": False, "error": "bridge not initialized"}

    op = req.get("op", "")
    try:
        if op == "ping":
            return {"ok": True, "data": {"pong": time.time()}}

        if op == "publish_command":
            _BRIDGE.publish_command(req.get("text", ""))
            return {"ok": True}

        if op == "publish_cmd_vel":
            _BRIDGE.publish_cmd_vel(
                float(req.get("linear", 0.0)),
                float(req.get("angular", 0.0)),
                float(req.get("duration", 1.0)),
            )
            return {"ok": True}

        if op == "publish_goal":
            _BRIDGE.publish_goal(
                float(req["x"]), float(req["y"]),
                float(req.get("yaw", 0.0)),
                req.get("frame", "map"),
            )
            return {"ok": True}

        if op == "get_scene":
            return {"ok": True, "data": _BRIDGE.latest_scene}

        if op == "get_detections":
            return {"ok": True, "data": _BRIDGE.latest_detections}

        if op == "get_pose":
            return {"ok": True, "data": _BRIDGE.latest_pose}

        if op == "get_image":
            if _BRIDGE.latest_image_bytes is None:
                return {"ok": False, "error": "no image received on /image_raw/compressed"}
            return {
                "ok": True,
                "data": {
                    "jpeg_base64": base64.b64encode(_BRIDGE.latest_image_bytes).decode("ascii"),
                    "ts": _BRIDGE.latest_image_ts,
                },
            }

        if op == "list_topics":
            return {"ok": True, "data": _BRIDGE.list_topics()}

        return {"ok": False, "error": f"unknown op: {op!r}"}

    except KeyError as e:
        return {"ok": False, "error": f"missing required field: {e}"}
    except Exception as e:
        logger.exception("handler error")
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


class _LineJsonHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        peer = self.client_address
        logger.info("client connected: %s", peer)
        try:
            for line in self.rfile:
                line = line.strip()
                if not line:
                    continue
                try:
                    req = json.loads(line)
                except json.JSONDecodeError as e:
                    self._write({"ok": False, "error": f"bad json: {e}"})
                    continue
                resp = _handle_request(req)
                self._write(resp)
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            logger.info("client disconnected: %s", peer)

    def _write(self, obj: Dict[str, Any]) -> None:
        self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.wfile.flush()


class _ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5556)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not ROS2_AVAILABLE:
        logger.error("rclpy not importable: %s", _IMPORT_ERROR)
        logger.error("Did you source /opt/ros/humble/setup.bash and ~/tron1_ws/install/setup.bash?")
        return 2

    rclpy.init()
    global _BRIDGE, _EXECUTOR
    _BRIDGE = HermesBridge()
    _EXECUTOR = SingleThreadedExecutor()
    _EXECUTOR.add_node(_BRIDGE)

    spin_thread = threading.Thread(target=_EXECUTOR.spin, daemon=True, name="rclpy-spin")
    spin_thread.start()

    server = _ThreadedServer((args.host, args.port), _LineJsonHandler)
    logger.info("sidecar listening on %s:%d", args.host, args.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        server.shutdown()
        _EXECUTOR.shutdown()
        _BRIDGE.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
