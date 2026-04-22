"""End-to-end demo: Hermes drives the Mac sim and reads the gauge with Qwen VL.

Assumes sim.py is already running (`python sim.py` in another terminal) and
the Hermes tron1_* tools are on PYTHONPATH.

Run:
    ~/.hermes/hermes-agent/venv/bin/python ~/tron1-sim-mac/demo.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/justinsuo/.hermes/hermes-agent")

from tools.tron1_ros2_tool import (  # noqa: E402
    _call, _handle_velocity, _handle_get_pose,
    _handle_get_image, _handle_get_scene,
)
from tools.qwen_vl_local_tool import qwen_vl_local  # noqa: E402


def drive_to(target_y: float, max_seconds: float = 12.0) -> dict:
    _handle_velocity({"linear": 1.0, "angular": 0, "duration": max_seconds})
    start = time.time()
    pose = {"y": -4.0}
    while time.time() - start < max_seconds + 0.5:
        time.sleep(0.25)
        pose = json.loads(_handle_get_pose({}))["data"]
        if pose["y"] > target_y:
            break
    _handle_velocity({"linear": 0, "angular": 0, "duration": 0.01})
    return pose


def main() -> int:
    print("== step 1: reset sim ==")
    print("   ", _call({"op": "reset"}))

    print("\n== step 2: what does the robot see from the start? ==")
    print("   ", _handle_get_scene({}))

    print("\n== step 3: drive toward the gauge ==")
    pose = drive_to(4.6)
    print(f"   final pose ({pose['x']:.2f}, {pose['y']:.2f})  yaw={pose['yaw']:.2f} rad")
    print("   scene after drive:", _handle_get_scene({}))

    print("\n== step 4: capture ego frame ==")
    img_resp = json.loads(_handle_get_image({}))
    path = img_resp["data"]["path"]
    saved = Path("/tmp/tron1_sim_last.jpg")
    shutil.copy(path, saved)
    print(f"   saved {saved}  ({os.path.getsize(saved)} bytes)")

    print("\n== step 5: Qwen VL reads the gauge ==")
    out = qwen_vl_local(
        path,
        ("You are a robot looking at an analog gauge on a wall. Read the "
         "needle's position. Return JSON only: "
         '{"value": <float>, "units": "<str>", "confidence": <float>}.'),
        max_tokens=100,
    )
    print(f"   qwen: {out['text'].strip()}")
    print(f"   latency: {out['latency_ms']} ms")

    print("\n== step 6: compare to sim ground truth ==")
    truth = _call({"op": "gauge_truth"})["data"]
    print(f"   truth: value={truth['value']}  units={truth['units']}")
    print(f"   needle_deg={truth['needle_deg']:+.1f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
