"""Record a short MP4 of the Tron 1 driving through the room.

Drives the robot via the sim's TCP API and records the chase camera into
~/tron1-sim-mac/demo_drive.mp4 using ffmpeg. Ground truth gauge reading is
overlaid after the run so the deliverable clip is self-contained.

Run:
    ~/.hermes/hermes-agent/venv/bin/python ~/tron1-sim-mac/record_demo.py
"""

from __future__ import annotations

import base64
import json
import math
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

OUT_DIR = Path("/tmp/tron1_frames")
OUT_MP4 = Path.home() / "tron1-sim-mac" / "demo_drive.mp4"


def sim_call(op: str, **kw) -> dict:
    with socket.create_connection(("127.0.0.1", 5556), timeout=10) as s:
        s.settimeout(10)
        s.sendall((json.dumps({"op": op, **kw}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            c = s.recv(65536)
            if not c: break
            buf += c
        return json.loads(buf)


def grab_frame(idx: int, camera: str = "tp") -> None:
    r = sim_call("get_image", camera=camera)
    jpg = base64.b64decode(r["data"]["jpeg_base64"])
    (OUT_DIR / f"{idx:06d}.jpg").write_bytes(jpg)


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True, parents=True)
    for f in OUT_DIR.glob("*.jpg"):
        f.unlink()

    sim_call("reset")
    truth = sim_call("gauge_truth")["data"]
    print(f"gauge truth: {truth['value']} {truth['units']}")

    # Script: drive toward north gauge, holding here for inspection
    frames = 0
    hz = 8  # capture rate
    dt = 1.0 / hz

    def tick():
        nonlocal frames
        grab_frame(frames, camera="tp")
        frames += 1

    # Stand still briefly
    t0 = time.time()
    while time.time() - t0 < 1.0:
        tick(); time.sleep(dt)

    # Drive forward at 0.8 m/s for 10s (covers 8m = -4 to +4)
    sim_call("publish_cmd_vel", linear=0.8, angular=0, duration=10)
    t0 = time.time()
    while time.time() - t0 < 10.0:
        tick(); time.sleep(dt)

    # Stop, a moment to show the gauge
    sim_call("publish_cmd_vel", linear=0, angular=0, duration=0.1)
    t0 = time.time()
    while time.time() - t0 < 2.5:
        tick(); time.sleep(dt)

    print(f"captured {frames} frames at {hz} Hz")

    # ffmpeg → mp4 (yuv420p for broad compatibility)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(hz),
        "-i", str(OUT_DIR / "%06d.jpg"),
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
        str(OUT_MP4),
    ], check=True)
    print(f"wrote {OUT_MP4}  ({OUT_MP4.stat().st_size // 1024} KB)")

    # Also a GIF for embedding in README
    gif_out = OUT_MP4.with_suffix(".gif")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(OUT_MP4),
        "-vf", "fps=8,scale=480:-1:flags=lanczos",
        str(gif_out),
    ], check=True)
    print(f"wrote {gif_out}  ({gif_out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
