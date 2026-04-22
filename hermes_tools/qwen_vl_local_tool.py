"""Local Qwen 2.5 VL vision tool for Hermes Agent (runs on MLX, Apple Silicon).

Exposes one LLM-callable tool:
    qwen_vl_local(image, prompt, max_tokens=...) -> description

The model is loaded lazily on first call and cached for the process lifetime.
Default: Qwen 2.5 VL 3B Instruct 4-bit MLX quant (~2.3 GB download once, ~3 GB
resident).  Override with HERMES_QWEN_VL_MODEL or HERMES_QWEN_VL_SIZE (3b|7b).

Use cases:
  * Photo from Telegram -> describe it offline with no API costs
  * /image_raw from the Tron 1 sim -> identify gauges, obstacles, doors
  * Verification step in the self-improvement loop (replaces CUA's Haiku check)

The Qwen 2.5 VL series understands:
  * Natural scene description
  * OCR (dial/gauge readings, signage, labels)
  * Spatial relations ("the chair is 2m left of the table")
  * Bounding-box style grounding when prompted for it
"""

import base64
import io
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

_SIZE_TO_REPO = {
    "3b": "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
    "7b": "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
}


def _resolve_model_repo() -> str:
    override = os.getenv("HERMES_QWEN_VL_MODEL", "").strip()
    if override:
        return override
    size = os.getenv("HERMES_QWEN_VL_SIZE", "3b").strip().lower()
    return _SIZE_TO_REPO.get(size, _SIZE_TO_REPO["3b"])


# ---------------------------------------------------------------------------
# Lazy model loader
# ---------------------------------------------------------------------------

_LOAD_LOCK = threading.Lock()
_CACHED_MODEL: Optional[Tuple[Any, Any, Any, str]] = None  # (model, processor, config, repo)


def _load_model():
    """Load + cache (model, processor, config). Called on first use only.

    Honors HERMES_QWEN_VL_ADAPTER: if set, applies a LoRA adapter (e.g. the
    gauge-reading adapter trained by tron1-selfplay/training/finetune_gauge.py).
    """
    global _CACHED_MODEL
    repo = _resolve_model_repo()
    adapter_path = os.getenv("HERMES_QWEN_VL_ADAPTER", "").strip() or None
    cache_key = f"{repo}|{adapter_path or ''}"
    with _LOAD_LOCK:
        if _CACHED_MODEL is not None and _CACHED_MODEL[3] == cache_key:
            return _CACHED_MODEL
        logger.info("loading qwen-vl model: %s (adapter=%s)", repo, adapter_path)
        from mlx_vlm import load
        from mlx_vlm.utils import load_config
        model, processor = load(repo)
        config = load_config(repo)
        if adapter_path:
            # apply_lora_layers expects a directory containing adapter_config.json;
            # if the user passed the safetensors file, strip the filename.
            adapter_dir = adapter_path
            if os.path.isfile(adapter_path):
                adapter_dir = os.path.dirname(adapter_path)
            try:
                from mlx_vlm.trainer import apply_lora_layers
                apply_lora_layers(model, adapter_dir)
                logger.info("applied LoRA adapter from %s", adapter_dir)
            except Exception as e:
                logger.warning("failed to apply adapter %s: %s", adapter_dir, e)
        _CACHED_MODEL = (model, processor, config, cache_key)
        logger.info("qwen-vl model ready")
        return _CACHED_MODEL


# ---------------------------------------------------------------------------
# Image normalization
# ---------------------------------------------------------------------------

def _normalize_image(image_arg: Any) -> str:
    """Accept a path, a base64 data URI, raw base64, or an HTTP URL.
    Return a local filesystem path the model can consume.
    """
    if isinstance(image_arg, str):
        # HTTP URL — mlx-vlm accepts it directly, but we cache to disk for determinism.
        if image_arg.startswith(("http://", "https://")):
            import urllib.request, tempfile
            path = tempfile.NamedTemporaryFile(
                prefix="qwen_vl_", suffix=".jpg", delete=False
            ).name
            urllib.request.urlretrieve(image_arg, path)
            return path

        # data: URI
        if image_arg.startswith("data:image"):
            _, _, b64 = image_arg.partition(",")
            return _write_b64_to_tempfile(b64)

        # Already a filesystem path
        p = Path(image_arg).expanduser()
        if p.exists():
            return str(p)

        # Best effort: treat as raw base64
        if len(image_arg) > 100:
            return _write_b64_to_tempfile(image_arg)

    raise ValueError("image must be a file path, http(s) url, data URI, or base64 string")


def _write_b64_to_tempfile(b64: str) -> str:
    import tempfile
    raw = base64.b64decode(b64, validate=False)
    suffix = ".jpg"
    if raw[:8].startswith(b"\x89PNG"):
        suffix = ".png"
    path = tempfile.NamedTemporaryFile(
        prefix="qwen_vl_", suffix=suffix, delete=False
    ).name
    with open(path, "wb") as f:
        f.write(raw)
    return path


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def qwen_vl_local(image: str, prompt: str, max_tokens: int = 256) -> Dict[str, Any]:
    """Run Qwen 2.5 VL on one image. Returns {text, latency_ms, model}."""
    img_path = _normalize_image(image)

    model, processor, config, repo = _load_model()
    from mlx_vlm import generate, apply_chat_template

    formatted = apply_chat_template(processor, config, prompt, num_images=1)

    t0 = time.time()
    result = generate(
        model, processor, formatted, image=img_path,
        max_tokens=int(max_tokens), verbose=False,
    )
    dt_ms = (time.time() - t0) * 1000.0

    # mlx_vlm.GenerationResult has a .text attribute in 0.4.x
    text = getattr(result, "text", None)
    if text is None:
        text = str(result)

    return {
        "text": text.strip(),
        "latency_ms": round(dt_ms, 1),
        "model": repo,
    }


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
    except ImportError as e:
        return json.dumps({
            "ok": False,
            "error": (
                f"mlx_vlm not importable ({e}). "
                "Install with: "
                "~/.hermes/hermes-agent/venv/bin/python -m pip install mlx-vlm"
            ),
        })
    except Exception as e:
        logger.exception("qwen_vl_local failed")
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})


def _check_available() -> bool:
    """Cheap availability check — does the package import? We do NOT load the
    model here; that would block tool-list enumeration for 30s on first use."""
    try:
        import mlx_vlm  # noqa: F401
        return True
    except ImportError:
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
        "a base64 string, or a data: URI. First call downloads ~2-5 GB of "
        "model weights and takes 30-60s; subsequent calls are fast (~1-3s)."
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
