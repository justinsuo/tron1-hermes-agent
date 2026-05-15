"""Mac-native MuJoCo simulation that speaks the same TCP JSON protocol as
~/ros2_sidecar/sidecar.py. Bypasses the VM+ROS 2 entirely so Hermes can drive
the sim directly on macOS.

Start:
    ~/.hermes/hermes-agent/venv/bin/python ~/tron1-sim-mac/sim.py --viewer

Then in another shell:
    export HERMES_ROS2_HOST=127.0.0.1 HERMES_ROS2_PORT=5556
    hermes
    > tron1_ping                   # pings the sim
    > tron1_velocity 0.5 0 1.5     # drive forward 1.5s
    > tron1_get_image              # grab ego camera frame
    > qwen_vl_local <that path> "What does the gauge read?"

Ops supported (subset of the VM sidecar — no rclpy needed):
    ping, publish_command, publish_cmd_vel, publish_goal,
    get_scene, get_detections, get_pose, get_image, list_topics

Extras beyond the VM sidecar:
    reset       - reset robot to start pose
    gauge_truth - returns the current gauge's ground-truth reading
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import math
import os
import queue
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import mujoco
    import numpy as np
    from PIL import Image
except ImportError as e:
    print(f"need mujoco, numpy, Pillow ({e})", file=sys.stderr)
    sys.exit(2)

try:
    import mujoco.viewer
    _VIEWER_OK = True
except ImportError:
    _VIEWER_OK = False

# Ensure gauge_render is importable when sim.py is run from any cwd
sys.path.insert(0, str(Path(__file__).parent))
import gauge_render

logger = logging.getLogger("tron1_sim_mac")

_ROOT = Path(__file__).parent
_SCENE = _ROOT / "assets" / "scene.xml"


# ---------------------------------------------------------------------------
# Simulation state
# ---------------------------------------------------------------------------

class Sim:
    def __init__(self, hz: float = 200.0):
        # Re-render gauges each launch for variety (N, E, W + legacy single)
        gauge_render.render_three(
            _ROOT / "assets",
            base_seed=int(time.time()) % 10_000,
        )
        self.model = mujoco.MjModel.from_xml_path(str(_SCENE))
        self.data = mujoco.MjData(self.model)

        # Identify robot free joint + cameras
        self.robot_qpos_start = self.model.jnt_qposadr[
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "robot_free")
        ]
        self.robot_qvel_start = self.model.jnt_dofadr[
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "robot_free")
        ]
        self.ego_cam_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, "ego")
        self.tp_cam_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, "tp")

        # The MuJoCo Renderer on macOS binds its GL context to the thread
        # that created it. ThreadingMixIn spawns a new thread per TCP
        # request, so creating the renderer lazily during a request would
        # work the first time and then hang silently from any other
        # thread (observed: get_image returning no data, no log entry).
        #
        # Fix: a dedicated render worker thread that exclusively owns the
        # GL context. All get_image() calls (regardless of which request
        # thread) enqueue a job onto _render_queue and wait on an event.
        self._renderer: Optional["mujoco.Renderer"] = None
        self._renderer_h = int(os.getenv("TRON1_RENDER_H", "240"))
        self._renderer_w = int(os.getenv("TRON1_RENDER_W", "320"))
        self._render_queue: queue.Queue = queue.Queue()
        self._render_worker_thread: Optional[threading.Thread] = None

        self.dt = 1.0 / hz
        self._stop = threading.Event()
        self._lock = threading.Lock()

        # Commanded velocities (body frame)
        self.cmd_linear = [0.0, 0.0]   # x,y in m/s
        self.cmd_angular = 0.0          # yaw rate rad/s
        self.cmd_expiry = 0.0           # unix ts when cmd reverts to zero

        self._last_command_text = ""
        self._last_wall = time.time()

        # Wheel spin joints — if present, sim.py rotates them at ω = v / r
        # so the wheels look like they're actually rolling. Purely visual.
        self._wheel_radius = 0.11  # matches wheel mesh
        self._wheel_joints: list[int] = []
        for jname in ("wheel_L_spin", "wheel_R_spin"):
            jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, jname)
            if jid >= 0:
                self._wheel_joints.append(self.model.jnt_qposadr[jid])

        self.reset()
        # Start the render worker now so the first get_image call doesn't
        # pay the thread-start latency.
        self._start_render_worker()

    def _rebuild_model(self) -> None:
        """Reload the MJCF + data from disk so freshly-written gauge PNGs
        are picked up. Cheap: ~100 ms. Called on reset when regen_gauges=true."""
        with self._lock:
            self.model = mujoco.MjModel.from_xml_path(str(_SCENE))
            self.data = mujoco.MjData(self.model)
            # Re-resolve joint/camera ids on the new model
            self.robot_qpos_start = self.model.jnt_qposadr[
                mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "robot_free")
            ]
            self.robot_qvel_start = self.model.jnt_dofadr[
                mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "robot_free")
            ]
            self.ego_cam_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, "ego")
            self.tp_cam_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, "tp")
            self._wheel_joints = []
            for jname in ("wheel_L_spin", "wheel_R_spin"):
                jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, jname)
                if jid >= 0:
                    self._wheel_joints.append(self.model.jnt_qposadr[jid])
            # The persistent Renderer is bound to the old self.model — close
            # and drop it so the next get_image() rebuilds against the new model.
            # On Apple Silicon the GL driver doesn't always release textures
            # immediately on close(); force a gc.collect() so any orphan
            # CPython refs get collected before we recreate.
            if self._renderer is not None:
                try:
                    self._renderer.close()
                except Exception:
                    pass
                self._renderer = None
                import gc as _gc
                _gc.collect()
            # Clear cached joint-qpos lookup since joint ids may have changed.
            self._joint_qposadr_cache = None

    def reset(self, pose: Optional[Tuple[float, float, float]] = None) -> None:
        """Reset robot. If pose=(x, y, yaw_rad) is given, teleport there;
        otherwise use the default start pose (0, -4, yaw=+90°)."""
        with self._lock:
            mujoco.mj_resetData(self.model, self.data)
            if pose is not None:
                x, y, yaw = float(pose[0]), float(pose[1]), float(pose[2])
            else:
                x, y, yaw = 0.0, -4.0, math.pi / 2
            qpos = self.data.qpos
            qpos[self.robot_qpos_start + 0] = x
            qpos[self.robot_qpos_start + 1] = y
            qpos[self.robot_qpos_start + 2] = 0.92  # Tron 1 base height when wheels on floor
            half = yaw * 0.5
            qpos[self.robot_qpos_start + 3] = math.cos(half)
            qpos[self.robot_qpos_start + 4] = 0.0
            qpos[self.robot_qpos_start + 5] = 0.0
            qpos[self.robot_qpos_start + 6] = math.sin(half)
            mujoco.mj_forward(self.model, self.data)
            self.cmd_linear = [0.0, 0.0]
            self.cmd_angular = 0.0
            self.cmd_expiry = 0.0
            self._initial_pose = {"x": x, "y": y, "z": 0.92, "yaw": yaw}

    def _apply_cmd(self) -> None:
        """Drive the robot kinematically by directly writing qpos each step.
        Physics still runs for collisions, but the base pose is forced —
        friction/armature don't fight commanded velocity. This makes the sim
        drivable without a trained walking policy."""
        now = time.time()
        active = now < self.cmd_expiry
        lin = self.cmd_linear if active else [0.0, 0.0]
        ang = self.cmd_angular if active else 0.0

        q = self.data.qpos[self.robot_qpos_start + 3 : self.robot_qpos_start + 7]
        siny = 2.0 * (q[0] * q[3] + q[1] * q[2])
        cosy = 1.0 - 2.0 * (q[2] * q[2] + q[3] * q[3])
        yaw = math.atan2(siny, cosy)

        # Kinematic update: advance pose by commanded velocity * dt_step.
        # mjData.time - self._last_cmd_t gives us the physics wall-time elapsed.
        dt = self.dt
        vx_w = lin[0] * math.cos(yaw) - lin[1] * math.sin(yaw)
        vy_w = lin[0] * math.sin(yaw) + lin[1] * math.cos(yaw)

        self.data.qpos[self.robot_qpos_start + 0] += vx_w * dt
        self.data.qpos[self.robot_qpos_start + 1] += vy_w * dt
        # Rotate the quaternion by ang * dt around Z
        dyaw = ang * dt
        cq, sq = math.cos(dyaw / 2), math.sin(dyaw / 2)
        w, x, y, z = q[0], q[1], q[2], q[3]
        # quat multiply: q * (cq, 0, 0, sq)
        nw = w * cq - z * sq
        nx = x * cq + y * sq
        ny = y * cq - x * sq
        nz = z * cq + w * sq
        self.data.qpos[self.robot_qpos_start + 3] = nw
        self.data.qpos[self.robot_qpos_start + 4] = nx
        self.data.qpos[self.robot_qpos_start + 5] = ny
        self.data.qpos[self.robot_qpos_start + 6] = nz
        # Zero qvel so physics doesn't add drift
        self.data.qvel[self.robot_qvel_start : self.robot_qvel_start + 6] = 0.0

        # Spin the wheels proportional to linear speed (ω = v / r). Purely
        # visual — the wheel mesh rotates so the robot looks like it's rolling,
        # not sliding. Both wheels spin the same way for pure forward motion;
        # differential spin when the yaw rate is non-zero (skid-steer).
        if self._wheel_joints:
            v = lin[0]  # forward speed
            w = ang
            wheel_base = 0.21  # m between wheels
            v_left  = v - w * wheel_base / 2
            v_right = v + w * wheel_base / 2
            omega_L = v_left / self._wheel_radius
            omega_R = v_right / self._wheel_radius
            if len(self._wheel_joints) >= 1:
                self.data.qpos[self._wheel_joints[0]] += omega_L * dt
            if len(self._wheel_joints) >= 2:
                self.data.qpos[self._wheel_joints[1]] += omega_R * dt

    def _wall_step(self) -> None:
        """Advance the kinematic robot by the elapsed wall time since the last
        call. Much cheaper than running physics at 100Hz: the robot is
        fully kinematic so we only need mj_forward before rendering."""
        now = time.time()
        # Clamp to avoid jumping huge distances after long idles (30+ s),
        # but allow up to 2s so a simple drive loop doesn't undercount.
        dt = max(0.0, min(2.0, now - self._last_wall))
        self._last_wall = now
        # Temporarily hijack self.dt so _apply_cmd uses the wall-time delta
        saved = self.dt
        self.dt = dt
        try:
            self._apply_cmd()
        finally:
            self.dt = saved
        mujoco.mj_forward(self.model, self.data)

    def step(self) -> None:
        """Kept for backwards-compat with the old physics-loop code path."""
        with self._lock:
            self._wall_step()

    # ----- Observation getters -----

    def get_pose(self) -> Dict[str, float]:
        with self._lock:
            self._wall_step()
            p = self.data.qpos[self.robot_qpos_start : self.robot_qpos_start + 3]
            q = self.data.qpos[self.robot_qpos_start + 3 : self.robot_qpos_start + 7]
            siny = 2.0 * (q[0] * q[3] + q[1] * q[2])
            cosy = 1.0 - 2.0 * (q[2] * q[2] + q[3] * q[3])
            yaw = math.atan2(siny, cosy)
            return {"x": float(p[0]), "y": float(p[1]), "z": float(p[2]),
                    "yaw": float(yaw)}

    def get_initial_pose(self) -> Dict[str, float]:
        """Pose captured at the most recent reset(). Used by locomotion
        graders to measure displacement against a known reference."""
        return dict(getattr(self, "_initial_pose", {}) or {})

    def get_imu(self) -> Dict[str, Any]:
        """Approximate IMU readout. The kinematic backend doesn't run real
        physics for the base, so angular velocity is the commanded yaw_rate
        (when a burst is active) and the orientation comes from the floating
        base quaternion."""
        with self._lock:
            q = list(self.data.qpos[self.robot_qpos_start + 3 : self.robot_qpos_start + 7])
            now = time.time()
            ang_z = float(self.cmd_angular) if now < self.cmd_expiry else 0.0
        return {
            "base_quat_wxyz": [float(q[0]), float(q[1]), float(q[2]), float(q[3])],
            "base_ang_vel": [0.0, 0.0, ang_z],
            "ts": time.time(),
        }

    # WF_TRON1A actuated joints, in the LimX-canonical order
    _ACTUATED_JOINTS = (
        "abad_L_Joint", "hip_L_Joint", "knee_L_Joint", "wheel_L_Joint",
        "abad_R_Joint", "hip_R_Joint", "knee_R_Joint", "wheel_R_Joint",
    )

    def _resolve_joint_qposadr(self) -> List[int]:
        """Cached lookup of qpos addresses for each actuated joint.
        Returns -1 for joints that are absent from the current MJCF (e.g. if
        the model omits the abad joints because the legs are mounted rigidly).
        """
        cached = getattr(self, "_joint_qposadr_cache", None)
        if cached is not None:
            return cached
        addrs: List[int] = []
        for jname in self._ACTUATED_JOINTS:
            jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, jname)
            addrs.append(int(self.model.jnt_qposadr[jid]) if jid >= 0 else -1)
        self._joint_qposadr_cache = addrs
        return addrs

    def get_joint_state(self) -> Dict[str, Any]:
        """Per-joint position/velocity in WF_TRON1A canonical order."""
        addrs = self._resolve_joint_qposadr()
        with self._lock:
            self._wall_step()
            pos: List[float] = []
            vel: List[float] = []
            for adr in addrs:
                if adr < 0:
                    pos.append(0.0)
                    vel.append(0.0)
                    continue
                pos.append(float(self.data.qpos[adr]))
                # qvel index ≠ qpos index for free joints; for hinge joints
                # the qvel index equals qpos index minus the floating-base
                # offset. Be safe: clamp into qvel range and fall back to 0.
                qvel_idx = adr - 1  # works for all hinge joints after the freejoint
                if 0 <= qvel_idx < len(self.data.qvel):
                    vel.append(float(self.data.qvel[qvel_idx]))
                else:
                    vel.append(0.0)
        return {
            "joint_names": list(self._ACTUATED_JOINTS),
            "joint_pos": pos,
            "joint_vel": vel,
            "ts": time.time(),
        }

    def get_image(self, camera: str = "ego", timeout: float = 10.0) -> bytes:
        """Render an off-screen camera frame as JPEG bytes.

        On macOS the GL context belongs to whichever thread created the
        Renderer; we forward all render work to a dedicated worker
        thread via ``_render_queue`` so it doesn't matter which TCP
        handler thread the caller is on.
        """
        if self._render_worker_thread is None or not self._render_worker_thread.is_alive():
            self._start_render_worker()
        evt = threading.Event()
        slot: dict = {"jpg": None, "err": None}
        self._render_queue.put((camera, evt, slot))
        if not evt.wait(timeout=timeout):
            raise TimeoutError(f"render worker did not respond within {timeout}s")
        if slot["err"]:
            raise slot["err"]
        return slot["jpg"]

    def _start_render_worker(self) -> None:
        """Spawn the singleton render worker thread."""
        if self._render_worker_thread is not None and self._render_worker_thread.is_alive():
            return
        t = threading.Thread(target=self._render_worker_loop, name="render-worker",
                             daemon=True)
        self._render_worker_thread = t
        t.start()

    def _render_worker_loop(self) -> None:
        """Owns the MuJoCo Renderer + its GL context. Lives for the
        duration of the Sim instance. Pulls jobs from _render_queue.

        We do not hold self._lock here for the entire duration — we only
        grab it briefly to copy out the data we need (camera id +
        mj_forward). Rendering itself then runs without blocking
        get_pose / health / etc. on other threads.
        """
        logger.info("render worker started (thread=%s)", threading.current_thread().name)
        while True:
            job = self._render_queue.get()
            if job is None:  # shutdown sentinel
                break
            camera, evt, slot = job
            try:
                with self._lock:
                    self._wall_step()
                    if camera == "ego":
                        cam_id = self.ego_cam_id
                    elif camera == "top":
                        # No dedicated 'top' camera in the MJCF; reuse tp
                        # which is the chase cam — close enough for the
                        # dashboard preview.
                        cam_id = self.tp_cam_id
                    else:
                        cam_id = self.tp_cam_id
                    if self._renderer is None:
                        self._renderer = mujoco.Renderer(
                            self.model,
                            height=self._renderer_h, width=self._renderer_w,
                        )
                    self._renderer.update_scene(self.data, camera=cam_id)
                pixels = self._renderer.render()
                img = Image.fromarray(pixels)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=75)
                slot["jpg"] = buf.getvalue()
            except Exception as e:
                logger.exception("render worker job failed: %s", e)
                slot["err"] = e
            finally:
                evt.set()

    # World positions of everything the "perception" layer knows about
    _LANDMARKS: Dict[str, Tuple[float, float]] = {
        "gauge_N": (0.0, 5.85),
        "gauge_E": (5.85, -1.5),
        "gauge_W": (-5.85, 2.0),
        "door": (5.88, 3.0),
        "box1": (-1.0, 1.5),
        "box2": (2.0, -1.5),
        "box3": (3.0, 2.0),
        "cone1": (-2.5, -0.5),
        "zone_charge": (-4.5, -4.0),
        "zone_home": (0.0, -4.0),
    }

    def detections(self) -> str:
        """Cheap stand-in: compute bboxes from known landmark positions
        relative to robot + camera FOV. A real perception node would YOLO."""
        pose = self.get_pose()
        detections = []
        for name, (x, y) in self._LANDMARKS.items():
            dx, dy = x - pose["x"], y - pose["y"]
            dist = math.hypot(dx, dy)
            bearing = math.atan2(dy, dx) - pose["yaw"]
            bearing = (bearing + math.pi) % (2 * math.pi) - math.pi
            # include what the ego camera could plausibly see (±50°)
            if abs(bearing) < math.radians(50):
                detections.append({
                    "class": name,
                    "distance_m": round(dist, 2),
                    "bearing_deg": round(math.degrees(bearing), 1),
                })
        return json.dumps(detections)

    def scene_description(self) -> str:
        dets = json.loads(self.detections())
        if not dets:
            return "Nothing notable in view."
        bits = [f"{d['class']} at {d['distance_m']}m ({d['bearing_deg']:+.0f}°)" for d in dets]
        return "I see: " + "; ".join(bits) + "."

    def gauge_truth(self, wall: str = "N") -> Dict[str, Any]:
        """Return ground-truth reading for the gauge on the given wall
        (N, E, W). Defaults to N for backwards compat."""
        wall = wall.upper()
        if wall in ("N", "E", "W"):
            path = _ROOT / "assets" / f"gauge_{wall}_truth.json"
        else:
            path = _ROOT / "assets" / "gauge_truth.json"
        return json.loads(path.read_text())

    def all_gauges_truth(self) -> Dict[str, Any]:
        p = _ROOT / "assets" / "gauges_truth.json"
        if p.exists():
            return json.loads(p.read_text())
        return {"N": self.gauge_truth()}

    def list_topics(self) -> Dict[str, str]:
        return {
            "/image_raw/compressed": "sensor_msgs/CompressedImage",
            "/cmd_vel":              "geometry_msgs/Twist",
            "/goal_pose":            "geometry_msgs/PoseStamped",
            "/perception/scene_description": "std_msgs/String",
            "/perception/detections":        "std_msgs/String",
            "/odom":                 "nav_msgs/Odometry",
        }


# ---------------------------------------------------------------------------
# TCP server (same protocol as ros2_sidecar/sidecar.py)
# ---------------------------------------------------------------------------

_SIM: Optional[Sim] = None


def _handle(req: Dict[str, Any]) -> Dict[str, Any]:
    if _SIM is None:
        return {"ok": False, "error": "sim not started"}
    op = req.get("op", "")

    try:
        if op == "ping":
            return {"ok": True, "data": {"pong": time.time(), "backend": "mujoco-mac"}}
        if op == "publish_command":
            _SIM._last_command_text = req.get("text", "")
            return {"ok": True}
        if op == "publish_cmd_vel":
            _SIM.cmd_linear = [float(req.get("linear", 0.0)), 0.0]
            _SIM.cmd_angular = float(req.get("angular", 0.0))
            _SIM.cmd_expiry = time.time() + float(req.get("duration", 1.0))
            return {"ok": True}
        if op == "publish_goal":
            # Point-to-point navigation stub: drive straight at it for a while.
            pose = _SIM.get_pose()
            tx, ty = float(req["x"]), float(req["y"])
            dx, dy = tx - pose["x"], ty - pose["y"]
            dist = math.hypot(dx, dy)
            if dist < 0.05:
                return {"ok": True, "data": "already there"}
            target_yaw = math.atan2(dy, dx)
            yaw_err = (target_yaw - pose["yaw"] + math.pi) % (2 * math.pi) - math.pi
            # turn first, then drive. Cheap but functional.
            _SIM.cmd_linear = [min(0.8, dist), 0.0]
            _SIM.cmd_angular = max(-1.0, min(1.0, yaw_err * 1.5))
            _SIM.cmd_expiry = time.time() + min(10.0, dist / 0.4)
            return {"ok": True, "data": {"distance": dist, "yaw_err": yaw_err}}
        if op == "get_pose":
            return {"ok": True, "data": _SIM.get_pose()}
        if op == "get_scene":
            return {"ok": True, "data": _SIM.scene_description()}
        if op == "get_detections":
            return {"ok": True, "data": _SIM.detections()}
        if op == "get_image":
            t0 = time.time()
            try:
                jpg = _SIM.get_image(camera=req.get("camera", "ego"))
            except Exception as e:
                logger.exception("get_image failed")
                return {"ok": False, "error": f"render failed: {type(e).__name__}: {e}"}
            logger.debug("rendered %d bytes in %.3fs", len(jpg), time.time() - t0)
            return {"ok": True, "data": {
                "jpeg_base64": base64.b64encode(jpg).decode("ascii"),
                "ts": time.time(),
            }}
        if op == "list_topics":
            return {"ok": True, "data": _SIM.list_topics()}
        if op == "reset":
            pose = None
            if "x" in req and "y" in req:
                pose = (float(req["x"]), float(req["y"]),
                        float(req.get("yaw", 0.0)))
            # Optional: re-render PNGs + rebuild the MuJoCo model so gauge
            # readings vary between episodes. Default off; pass regen=true.
            if req.get("regen_gauges"):
                try:
                    gauge_render.render_three(
                        _ROOT / "assets",
                        base_seed=int(time.time() * 1000) % 10**6,
                    )
                    _SIM._rebuild_model()
                except Exception as e:
                    logger.warning("gauge regen failed: %s", e)
            _SIM.reset(pose)
            return {"ok": True}
        if op == "gauge_truth":
            wall = req.get("wall", "N")
            return {"ok": True, "data": _SIM.gauge_truth(wall)}
        if op == "all_gauges_truth":
            return {"ok": True, "data": _SIM.all_gauges_truth()}
        if op == "get_initial_pose":
            return {"ok": True, "data": _SIM.get_initial_pose()}
        if op == "get_imu":
            return {"ok": True, "data": _SIM.get_imu()}
        if op == "get_joint_state":
            return {"ok": True, "data": _SIM.get_joint_state()}
        if op == "health":
            import os as _os
            import resource
            ru = resource.getrusage(resource.RUSAGE_SELF)
            return {"ok": True, "data": {
                "rss_mb": ru.ru_maxrss / (1024 * 1024) if ru.ru_maxrss > 10**7 else ru.ru_maxrss / 1024,
                "pid": _os.getpid(),
                "renderer_alive": _SIM._renderer is not None,
                "render_h": _SIM._renderer_h,
                "render_w": _SIM._renderer_w,
                "ts": time.time(),
            }}
        return {"ok": False, "error": f"unknown op: {op!r}"}
    except Exception as e:
        logger.exception("handler error")
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


class _LineJson(socketserver.StreamRequestHandler):
    def handle(self) -> None:
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
                self._write(_handle(req))
        except (ConnectionResetError, BrokenPipeError):
            pass

    def _write(self, obj):
        self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.wfile.flush()


class _ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5556)
    p.add_argument("--hz", type=float, default=200.0)
    p.add_argument("--viewer", action="store_true",
                   help="Open the MuJoCo passive viewer window (Mac friendly).")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    global _SIM
    _SIM = Sim(hz=args.hz)
    truth = _SIM.gauge_truth()
    logger.info("sim ready. gauge truth: %s %s", truth["value"], truth["units"])

    server = _ThreadedServer((args.host, args.port), _LineJson)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True, name="tcp")
    server_thread.start()
    logger.info("listening on %s:%d", args.host, args.port)

    if args.viewer and _VIEWER_OK:
        # passive viewer: the caller (this thread) advances physics and the
        # viewer renders from the same mjData.
        try:
            with mujoco.viewer.launch_passive(_SIM.model, _SIM.data) as viewer:
                # Preset the viewer camera to the scene's tp camera so the
                # whole room + robot are framed on open.
                try:
                    tp_id = mujoco.mj_name2id(_SIM.model, mujoco.mjtObj.mjOBJ_CAMERA, "tp")
                    if tp_id >= 0:
                        viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
                        viewer.cam.fixedcamid = tp_id
                except Exception as e:
                    logger.warning("couldn't set tp camera: %s", e)
                while viewer.is_running():
                    _SIM.step()
                    viewer.sync()
                    time.sleep(max(0.0, _SIM.dt - 0.001))
        except KeyboardInterrupt:
            pass
    else:
        if args.viewer and not _VIEWER_OK:
            logger.warning("mujoco.viewer not available; running headless")
        # Headless: physics advances lazily inside TCP handlers. Just idle
        # on the main thread.
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass

    _SIM._stop.set()
    server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
