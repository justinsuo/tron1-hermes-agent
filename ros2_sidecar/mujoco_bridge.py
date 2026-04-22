"""MuJoCo ↔ ROS 2 bridge for the Tron 1 sim.

Runs inside the Ubuntu VM alongside ``tron1-mujoco-sim``. Exposes the MuJoCo
renderer's camera and physics state on the same ROS 2 topics that the Unity
and Unreal sims (eventually) publish.

This lets you exercise the full Hermes → sidecar → ROS 2 → sim loop *today*,
without waiting for the game-engine sims to be built. Swap the backend by
starting whichever sim you want — the topics are identical.

Start (inside the VM, after the existing simulator.py is running):
    source /opt/ros/humble/setup.bash
    source ~/tron1_ws/install/setup.bash
    python3 mujoco_bridge.py \\
        --model ~/tron1-mujoco-sim/robots/WF_TRON1A/scene.xml \\
        --hz 30

Required python packages (already present in the tron1-mujoco-sim env):
    mujoco>=3.0, rclpy, numpy, Pillow
"""

from __future__ import annotations

import argparse
import io
import math
import sys
import time

try:
    import mujoco
    import numpy as np
    from PIL import Image
except ImportError as e:
    print(f"mujoco/numpy/Pillow required: {e}", file=sys.stderr)
    sys.exit(2)

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from std_msgs.msg import String
    from geometry_msgs.msg import Twist, PoseStamped
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import CompressedImage
except ImportError as e:
    print(f"rclpy not importable ({e}). Did you source /opt/ros/humble/setup.bash?", file=sys.stderr)
    sys.exit(2)


class MujocoBridge(Node):
    def __init__(self, model_path: str, hz: float = 30.0, cam_name: str = "camera"):
        super().__init__("mujoco_bridge")
        self.model = mujoco.MjModel.from_xml_path(model_path)
        self.data = mujoco.MjData(self.model)
        self.renderer = mujoco.Renderer(self.model, height=480, width=640)

        # Resolve camera id
        try:
            self.cam_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, cam_name)
            if self.cam_id < 0:
                self.cam_id = 0  # fallback
        except Exception:
            self.cam_id = 0

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                         history=HistoryPolicy.KEEP_LAST, depth=10)
        self.pub_image = self.create_publisher(CompressedImage, "/image_raw/compressed", qos)
        self.pub_odom = self.create_publisher(Odometry, "/odom", qos)
        self.pub_scene = self.create_publisher(String, "/perception/scene_description", qos)

        self.create_subscription(Twist, "/cmd_vel", self._on_twist, qos)
        self.create_subscription(PoseStamped, "/goal_pose", self._on_goal, qos)

        self.get_logger().info(f"MuJoCo bridge up: model={model_path}, cam_id={self.cam_id}")

        period = 1.0 / max(1.0, float(hz))
        self.create_timer(period, self._tick)

        self._twist = Twist()
        self._step_count = 0

    def _on_twist(self, msg: Twist) -> None:
        self._twist = msg

    def _on_goal(self, msg: PoseStamped) -> None:
        self.get_logger().info(
            f"goal received at x={msg.pose.position.x:.2f} y={msg.pose.position.y:.2f}"
        )

    def _tick(self) -> None:
        # Apply a simple holonomic velocity to the base body. For the wheeled
        # Tron 1 this is a stand-in; the real RL policy handles walking.
        # Base qpos layout depends on the URDF — we set root linear vel only.
        try:
            self.data.qvel[0] = float(self._twist.linear.x)
            self.data.qvel[1] = float(self._twist.linear.y)
            self.data.qvel[5] = float(self._twist.angular.z)
        except IndexError:
            pass  # non-free-joint model, skip

        mujoco.mj_step(self.model, self.data)

        self._publish_image()
        self._publish_odom()
        if self._step_count % 10 == 0:
            self._publish_scene()
        self._step_count += 1

    def _publish_image(self) -> None:
        self.renderer.update_scene(self.data, camera=self.cam_id)
        pixels = self.renderer.render()  # HxWx3 RGB uint8
        img = Image.fromarray(pixels)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        msg = CompressedImage()
        msg.header.frame_id = "camera_link"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = "jpeg"
        msg.data = buf.getvalue()
        self.pub_image.publish(msg)

    def _publish_odom(self) -> None:
        msg = Odometry()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"
        msg.header.stamp = self.get_clock().now().to_msg()
        try:
            msg.pose.pose.position.x = float(self.data.qpos[0])
            msg.pose.pose.position.y = float(self.data.qpos[1])
            msg.pose.pose.position.z = float(self.data.qpos[2])
            # free-joint quaternion stored as (w,x,y,z)
            w, x, y, z = (float(self.data.qpos[i]) for i in (3, 4, 5, 6))
            msg.pose.pose.orientation.w = w
            msg.pose.pose.orientation.x = x
            msg.pose.pose.orientation.y = y
            msg.pose.pose.orientation.z = z
        except IndexError:
            pass
        self.pub_odom.publish(msg)

    def _publish_scene(self) -> None:
        # Stub narration; a fuller perception node would run YOLO here.
        m = String()
        m.data = f"mujoco sim running step={self._step_count}, cmd_vel_linear_x={self._twist.linear.x:.2f}"
        self.pub_scene.publish(m)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True, help="Path to the MuJoCo scene XML.")
    p.add_argument("--hz", type=float, default=30.0)
    p.add_argument("--cam", default="camera", help="MuJoCo camera name.")
    args = p.parse_args()

    rclpy.init()
    node = MujocoBridge(args.model, hz=args.hz, cam_name=args.cam)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
