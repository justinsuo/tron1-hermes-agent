"""Local Qwen 2.5 VL vision tool for Hermes Agent (HTTP client to mlx_vlm.server).

Exposes one LLM-callable tool:
    qwen_vl_local(image, prompt, max_tokens=...) -> description

IMPORTANT — why this is an HTTP client and not an in-process model loader:

  The previous version loaded Qwen 2.5 VL (~3 GB) *inside the calling
  process* and cached it "for the process lifetime". In self-play, the
  calling process is a fresh `hermes chat` subprocess spawned per episode,
  so that 3 GB model was loaded and discarded every single episode. On
  Apple Silicon (unified memory, GPU shares RAM) that churned multi-GB
  Metal allocations until the whole Mac hung — root-caused via the Phase-3
  bisection on 2026-05-15.

  Fix: the VL model now runs as ONE persistent server (mlx_vlm.server,
  started by tron1-sim-mac/mlx_vlm_server_keepalive.sh on :8081). This tool
  is a thin HTTP client. The model is loaded exactly once, no matter how
  many hermes subprocesses spawn.

Environment variables:
  HERMES_QWEN_VL_URL    Base URL of the VL server. Default http://127.0.0.1:8081
  HERMES_QWEN_VL_MODEL  Model id to request. Default mlx-community/Qwen2.5-VL-3B-Instruct-4bit
  HERMES_QWEN_VL_TIMEOUT  Per-request timeout in seconds. Default 90.

Use cases:
  * Photo from Telegram -> describe it offline with no API costs
  * /image_raw from the Tron 1 sim -> identify gauges, obstacles, doors
  * Verification step in the self-improvement loop
"""

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://127.0.0.1:8081"
_DEFAULT_MODEL = "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"
_DEFAULT_TIMEOUT = 90.0


def _server_url() -> str:
    return os.getenv("HERMES_QWEN_VL_URL", _DEFAULT_URL).rstrip("/")


def _model_id() -> str:
    # HERMES_QWEN_VL_MODEL kept for back-compat; HERMES_QWEN_VL_SIZE maps 3b/7b.
    override = os.getenv("HERMES_QWEN_VL_MODEL", "").strip()
    if override:
        return override
    size = os.getenv("HERMES_QWEN_VL_SIZE", "3b").strip().lower()
    return {
        "3b": "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
        "7b": "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
    }.get(size, _DEFAULT_MODEL)


# ---------------------------------------------------------------------------
# Image normalization → base64 (for embedding in an OpenAI image_url data URI)
# ---------------------------------------------------------------------------

def _image_to_data_uri(image_arg: Any) -> str:
    """Accept a path, data URI, raw base64, or http(s) URL. Return a
    `data:image/...;base64,...` URI the VL server can consume."""
    if not isinstance(image_arg, str):
        raise ValueError("image must be a string (path, url, base64, or data URI)")

    # Already a data URI — pass through.
    if image_arg.startswith("data:image"):
        return image_arg

    # HTTP URL — fetch the bytes ourselves so the request is self-contained.
    if image_arg.startswith(("http://", "https://")):
        with urllib.request.urlopen(image_arg, timeout=30) as r:
            raw = r.read()
        return _bytes_to_data_uri(raw)

    # Filesystem path. Guard exists() — a raw base64 blob is far longer
    # than any real path and makes os.stat raise ENAMETOOLONG.
    if len(image_arg) < 1024:
        try:
            p = Path(image_arg).expanduser()
            if p.exists():
                return _bytes_to_data_uri(p.read_bytes())
        except OSError:
            pass

    # Best effort: treat as raw base64 (the common case for sim images
    # passed straight through from tron1_get_image's jpeg_base64).
    if len(image_arg) > 100:
        try:
            raw = base64.b64decode(image_arg, validate=False)
            if raw[:3] == b"\xff\xd8\xff" or raw[:8].startswith(b"\x89PNG"):
                return _bytes_to_data_uri(raw)
        except Exception:
            pass

    raise ValueError("image must be a file path, http(s) url, data URI, or base64 string")


def _bytes_to_data_uri(raw: bytes) -> str:
    mime = "image/png" if raw[:8].startswith(b"\x89PNG") else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


# ---------------------------------------------------------------------------
# Core call — HTTP to the persistent VL server
# ---------------------------------------------------------------------------

def qwen_vl_local(image: str, prompt: str, max_tokens: int = 256) -> Dict[str, Any]:
    """Run Qwen 2.5 VL on one image via the persistent mlx_vlm server.
    Returns {text, latency_ms, model}."""
    data_uri = _image_to_data_uri(image)
    model = _model_id()
    timeout = float(os.getenv("HERMES_QWEN_VL_TIMEOUT", str(_DEFAULT_TIMEOUT)))

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }],
        "max_tokens": int(max_tokens),
    }
    req = urllib.request.Request(
        _server_url() + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read().decode("utf-8"))
    dt_ms = (time.time() - t0) * 1000.0

    choices = resp.get("choices") or []
    text = ""
    if choices:
        text = (choices[0].get("message") or {}).get("content", "") or ""

    return {
        "text": text.strip(),
        "latency_ms": round(dt_ms, 1),
        "model": model,
    }


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def _handle_qwen_vl(args: Dict[str, Any], **_: Any) -> str:
    try:
        image = args.get("image") or args.get("image_path")
        prompt = args.get("prompt") or ""
        max_tokens = int(args.get("max_tokens", 256))
    except Exception as e:
        return json.dumps({"ok": False, "error": f"bad args: {e}"})

    if not image:
        return json.dumps({"ok": False, "error": "image is required (path, url, or base64)"})
    if not prompt:
        return json.dumps({"ok": False, "error": "prompt is required"})

    try:
        out = qwen_vl_local(image, prompt, max_tokens=max_tokens)
        return json.dumps({"ok": True, "data": out})
    except urllib.error.URLError as e:
        return json.dumps({
            "ok": False,
            "error": (
                f"VL server unreachable at {_server_url()} ({e}). "
                "Start it with: "
                "nohup ~/tron1-sim-mac/mlx_vlm_server_keepalive.sh "
                "> /tmp/mlx-vlm-keepalive.log 2>&1 &"
            ),
        })
    except Exception as e:
        logger.exception("qwen_vl_local failed")
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})


def _check_available() -> bool:
    """Cheap availability check — is the VL server reachable? We do a fast
    /health probe; never load a model in-process (that was the crash bug)."""
    try:
        with urllib.request.urlopen(_server_url() + "/health", timeout=1.0) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Schema + registration
# ---------------------------------------------------------------------------

QWEN_VL_SCHEMA = {
    "name": "qwen_vl_local",
    "description": (
        "Run Qwen 2.5 VL (local, offline, MLX on Apple Silicon) on a single "
        "image with a natural-language prompt. Good for gauge/meter reading, "
        "OCR, object recognition, scene description, and spatial questions. "
        "The image can be a local file path, a file:// url, an http(s) url, "
        "a base64 string, or a data: URI. Runs against a persistent VL "
        "server (loaded once); calls are fast (~1-3s)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image": {
                "type": "string",
                "description": (
                    "Path, URL, or base64 of the image to analyze. For photos "
                    "from the Tron 1 camera, pass the `path` field returned by "
                    "tron1_get_image."
                ),
            },
            "prompt": {
                "type": "string",
                "description": (
                    "What to ask about the image. Be specific, e.g. "
                    "'What does this pressure gauge read in PSI?' or "
                    "'List every obstacle in the scene with its approximate "
                    "position in the robot\\'s frame.'"
                ),
            },
            "max_tokens": {
                "type": "integer",
                "description": "Cap on response length. Default 256.",
            },
        },
        "required": ["image", "prompt"],
    },
}

from tools.registry import registry

registry.register(
    name="qwen_vl_local",
    toolset="vision_local",
    schema=QWEN_VL_SCHEMA,
    handler=_handle_qwen_vl,
    check_fn=_check_available,
    emoji="👁️",
)
