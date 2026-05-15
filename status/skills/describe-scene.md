---
title: Describe-Scene
version: 1.0
name: describe-scene
description: Use when the user asks "what do you see?" or a task needs a grounded visual summary of what's in front of the Tron 1 robot. Returns a structured description usable by other skills.
---
## Failure notes
- Ensure the description includes at least 3 distinct keywords to avoid being flagged as too thin.
- Avoid generic descriptions; include specific objects, colors, or actions observed.
- Avoid generic descriptions; include specific objects, colors, or actions observed.

- Ensure the description includes at least 3 distinct keywords to avoid being flagged as too thin.


## Purpose
## Failure notes
- Ensure the description includes at least 3 distinct keywords to avoid being flagged as too thin.
- Avoid generic descriptions; include specific objects, colors, or actions observed.
- Avoid generic descriptions; include specific objects, colors, or actions observed.

- Ensure the description includes at least 3 distinct keywords to avoid being flagged as too thin.


## Workflow
1. Use `tron1_get_image` to capture the latest camera frame.
2. Use `qwen_vl_local` with the prompt: 'Describe the scene in detail, including any gauges, doors, obstacles, floor markers, or walls visible.'
3. Format the output as a structured report with the following sections:
   - Walls
   - Floor
   - Obstacles
   - Doors
## Failure notes
- Ensure the description includes at least 3 distinct keywords to avoid being flagged as too thin.
- Avoid generic descriptions; include specific objects, colors, or actions observed.
- Avoid generic descriptions; include specific objects, colors, or actions observed.

- Ensure the description includes at least 3 distinct keywords to avoid being flagged as too thin.


## Example
```text
Walls: ...
Floor: ...
Obstacles: ...
Doors: ...
Gauges: ...
```