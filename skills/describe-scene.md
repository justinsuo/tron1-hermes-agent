---
name: describe-scene
description: Use when the user asks "what do you see?" or a task needs a grounded visual summary of what's in front of the Tron 1 robot. Returns a structured description usable by other skills.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, tron1, vision, perception, scene]
    related_skills: [read-wall-gauge, avoid-obstacle]
---

# Describe Scene

## Overview

Grab the latest camera frame and produce a structured scene description with
notable objects, approximate layout, and any action-relevant cues (doors,
gauges, obstacles, people, signage).

This is the bread-and-butter "eyes" of the robot — most other robotics skills
start by calling this and then branching.

## Procedure

1. Call `tron1_get_image`. Keep the `path`.
2. Call `qwen_vl_local` with:
   - `image`: the path
   - `prompt` (verbatim):
     > "You are a robot vision system. Describe this scene in JSON with keys:
     > `summary` (one sentence), `objects` (list of `{name, approx_position, notes}`
     > with positions like 'left', 'center', 'right', 'far', 'near'),
     > `gauges_or_meters` (list of any analog/digital readouts visible),
     > `obstacles` (list of things the robot should avoid),
     > `doors_or_exits` (list of openings), `notable_text` (any readable signage).
     > Return JSON only."
   - `max_tokens`: 400
3. Attempt `json.loads`. If it fails, keep the raw text under key `raw`.
4. Return `{path, scene_json}` to the caller.

## When to Use

- Any time an agent needs grounded scene context before acting.
- At the start of `read-wall-gauge`, `avoid-obstacle`, `find-door` skills.
- When the user simply asks "what are you looking at?".

## Cost / latency notes

On the 3B 4-bit Qwen 2.5 VL model with a 480p frame, expect ~1.5–4 s per call
on M-series Mac. The 7B variant is ~2× slower but noticeably better at OCR
and fine obstacle recognition; switch by setting
`HERMES_QWEN_VL_SIZE=7b` in the shell environment.

## Lessons

- Obstacle counts may be overestimated by the 3B model; use 7B variant or manual verification for precise counts in count-obstacles tasks.
