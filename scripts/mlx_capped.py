"""Run an mlx_lm / mlx_vlm server with HARD MLX memory caps.

Root cause of the Tron 1 crash loop (found 2026-05-15 via the Phase-3
bisection + memory-guardian instrumentation): MLX on Apple Silicon
allocates Metal GPU buffers in the unified memory pool and *wires* them
(non-pageable). Its buffer cache grew unbounded across repeated inference
calls — image inference on the VL model especially — until wired memory
filled physical RAM and the kernel hung the whole Mac. The ballooning
memory never showed up in process RSS, which is why every earlier fix
missed it.

This wrapper sets, before the server loads anything:
  mx.set_memory_limit  — hard ceiling on total MLX allocation
  mx.set_cache_limit   — ceiling on the buffer cache (small = free
                         buffers instead of hoarding them)
  mx.set_wired_limit   — ceiling on wired (non-pageable) memory — the
                         single most important cap, since wired memory
                         is what hangs the kernel.

Usage:
  python mlx_capped.py mlx_lm server --model ...
  python mlx_capped.py mlx_vlm.server --model ...

Env (GB):
  MLX_MEM_LIMIT_GB    default 8
  MLX_CACHE_LIMIT_GB  default 0.5
  MLX_WIRED_LIMIT_GB  default 8
"""

import os
import runpy
import sys

import mlx.core as mx


def _gb(env: str, default: float) -> int:
    try:
        return int(float(os.getenv(env, str(default))) * 1e9)
    except ValueError:
        return int(default * 1e9)


mem_limit = _gb("MLX_MEM_LIMIT_GB", 8)
cache_limit = _gb("MLX_CACHE_LIMIT_GB", 0.5)
wired_limit = _gb("MLX_WIRED_LIMIT_GB", 8)

for name, fn, val in (
    ("memory_limit", mx.set_memory_limit, mem_limit),
    ("cache_limit", mx.set_cache_limit, cache_limit),
    ("wired_limit", mx.set_wired_limit, wired_limit),
):
    try:
        fn(val)
        print(f"[mlx_capped] {name} = {val/1e9:.1f} GB", flush=True)
    except Exception as e:  # noqa: BLE001 — never let a cap failure block startup
        print(f"[mlx_capped] WARN could not set {name}: {e}", flush=True)

if len(sys.argv) < 2:
    print("usage: python mlx_capped.py <module> [args...]", file=sys.stderr)
    sys.exit(2)

module = sys.argv[1]
sys.argv = sys.argv[1:]  # shift so the server sees a normal argv
runpy.run_module(module, run_name="__main__", alter_sys=True)
