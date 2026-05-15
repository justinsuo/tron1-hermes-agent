# Contributing

This is primarily a personal project — but the code, the tests, and the
architectural choices are open for anyone to learn from, fork, or
improve.

## Quick start for hacking

```bash
git clone https://github.com/justinsuo/tron1-hermes-agent
cd tron1-hermes-agent

# 1. Build the clickable .app (optional but easiest)
bash scripts/build_app.sh

# 2. Or run components manually
./scripts/start_all.sh                    # sim + dashboard
./scripts/start_all.sh viewer             # + MuJoCo native 3D window
./scripts/start_all.sh selfplay 20        # + 20 self-play episodes

# 3. Run the test suite
~/.hermes/hermes-agent/venv/bin/python -m pytest tests -q
```

You'll need:

- macOS on Apple Silicon (M1+)
- Hermes Agent installed at `~/.hermes/hermes-agent/`
  ([installer](https://github.com/NousResearch/hermes-agent))
- MLX (`pip install mlx mlx-lm mlx-vlm`)
- MuJoCo (`pip install mujoco`)
- A Qwen 3 4B 4-bit checkpoint cached via Hugging Face
  (`mlx-community/Qwen3-4B-4bit` — automatic on first run)

## Layout reminder

| Folder | Pinned to live disk location |
|---|---|
| `sim/sim.py` | mirror of `/Users/justinsuo/tron1-sim-mac/sim.py` |
| `dashboard/dashboard_server.py` | mirror of `/Users/justinsuo/tron1-sim-mac/dashboard_server.py` |
| `selfplay/*.py` | mirror of `/Users/justinsuo/tron1-selfplay/*.py` |
| `hermes_tools/*.py` | mirror of `/Users/justinsuo/.hermes/hermes-agent/tools/*.py` |
| `skills/*.md` | mirror of `~/.hermes/skills/robotics/*/SKILL.md` |

`scripts/sync_to_repo.sh` runs every 10 min and copies the live files
into the repo so the GitHub front page shows current state. **Edits
made inside the repo without also updating the live copies will be
overwritten by the next sync.** For most edits you want to make changes
in the live location and let the sync mirror them.

## Style conventions

The codebase deliberately follows a few principles to stay grep-able
and reviewable:

1. **Comments explain *why*, not *what*.** Variable names already say
   what. Comments earn their place when they record a non-obvious
   constraint or a past incident the next reader needs to know.
2. **Defaults are safe.** New parameters default to whatever the
   previous behavior was. Breaking changes get a separate PR + a
   `CHANGELOG.md` entry.
3. **Failures return structured errors, never exceptions across
   subprocess boundaries.** Hermes tools return `{"ok": false,
   "error": "..."}`; they don't raise.
4. **No emoji in code.** They're fine in commit messages / READMEs /
   skill files.
5. **One commit per change, with a descriptive subject line.** Auto-sync
   commits use the `auto: sync · ...` prefix so they're easy to filter.

## Running self-play

```bash
# one-off 20 episodes
~/.hermes/hermes-agent/venv/bin/python ~/tron1-selfplay/robotics_selfplay.py \
    --rounds 20 --delay 20

# overnight via supervisor (4-12 h)
DURATION_SEC=43200 BATCH_ROUNDS=20 BATCH_DELAY=20 \
    bash ~/tron1-selfplay/supervisor.sh
```

Watch progress live in the browser at `http://127.0.0.1:5557/` or via
the watchdog log at `/tmp/tron1-watchdog.log`.

## Adding a new self-play task

```python
# selfplay/tasks.py (or selfplay/locomotion_tasks.py for locomotion)
def _grade_my_task(transcript, sim):
    pose = sim.get("pose") or {}
    # ...
    return (success, reward, reason)

TASKS.append(Task(
    id="my-task",
    prompt="Drive forward 2m and report the door state.",
    budget_s=120,
    weight=1.0,
    grade=_grade_my_task,
    reset_to=(0.0, -4.0, math.pi / 2),
))
```

The weighted sampler in `_sample_task()` automatically picks it up. If
the task should boost in frequency after recent failures, the existing
`failure_boost` mechanism handles that.

## Adding a new Hermes tool

```python
# hermes_tools/my_tool.py
def _handle_my_tool(args, **_):
    # ... do work ...
    return json.dumps({"ok": True, "data": {...}})

MY_TOOL_SCHEMA = {
    "name": "my_tool",
    "description": "...",
    "parameters": {"type": "object", "properties": {...}, "required": []},
}

from tools.registry import registry
registry.register(
    name="my_tool",
    toolset="tron1",
    schema=MY_TOOL_SCHEMA,
    handler=_handle_my_tool,
)
```

Hermes auto-discovers tools by AST-walking the `tools/` directory for
top-level `registry.register(...)` calls. A `for`-loop or function
wrapping the call **will not** be discovered.

## Submitting changes

1. Fork → branch → commit.
2. Make sure `pytest tests -q` still passes.
3. PR against `main` with a clear description: what you changed, why,
   and how to test it.
4. CI runs the test suite. If it passes, expect review within a few
   days.

## Reporting bugs

GitHub Issues. Please include:

- macOS version + chip (`uname -a`).
- Recent state from `tail -200 ~/.tron1-robotics-log.jsonl`.
- If a crash: `tail /tmp/tron1-sim.log /tmp/tron1-dashboard.log
  /tmp/tron1-watchdog.log`.
- A short reproducer if you can.

## License

MIT — see [LICENSE](LICENSE). By contributing you agree to license
your contribution under the same terms.
