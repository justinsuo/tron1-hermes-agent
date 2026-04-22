---
name: read-wall-gauge
description: Use when the user or a task asks the Tron 1 robot to read a wall-mounted analog gauge (pressure, temperature, fluid level, etc.). Approaches, frames the gauge, and returns a numeric reading with units.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, tron1, vision, gauge, inspection]
    related_skills: [avoid-obstacle, describe-scene]
---

# Read a Wall Gauge

## Overview

The robot approaches a wall-mounted analog gauge, centers it in the camera
frame, captures an image, runs the local Qwen 2.5 VL on it, and returns a
structured reading `{value, units, confidence}`.

This is the canonical "industrial inspection" skill — the same pattern applies
to thermostats, electrical meters, pressure gauges, valve handles, etc.

## When to Use

Use this skill when:

- The user asks "what does the [gauge/meter/dial] read?"
- A scheduled inspection task fires
- The perception pipeline detects a `gauge` or `dial` class and the user wants a value

Do **not** use for digital readouts — those are better served by generic OCR.

## Required tools

- `tron1_get_scene` — confirm a gauge is visible
- `tron1_get_image` — capture a frame
- `tron1_velocity` or `tron1_goto` — small positioning adjustments
- `qwen_vl_local` — the actual reading (offline, via MLX)

## Procedure

1. **Locate the gauge.**
   Call `tron1_get_scene` (or `tron1_get_detections`) and look for keywords:
   `gauge`, `dial`, `meter`, `pressure`, `thermostat`. If none, politely tell
   the user "I don't see a gauge — can you steer me toward one?".

2. **Frame the gauge.**
   Ideal capture distance is ~1.1–1.25 m with the gauge centered and parallel
   to the sensor plane. If the gauge is off-center or tilted, issue small
   corrections with `tron1_velocity` (≤ 0.2 m/s for 0.3–0.8 s at a time) and
   re-capture.

   **Stopping-distance heuristic (learned 2026-04-17 on the Mac sim):**
   if the gauge wall is at `y=5.85` and the robot starts at `y=-4`, stop at
   `y≈4.65` (distance 1.20 m). At `y>4.75` the top of the dial clips out of
   frame and the VLM mis-reads. At `y<4.2` the gauge is too small. Check
   with `tron1_get_pose` after each 1-second drive burst and halt early.
   - 2026-04-21 run: `tron1_goto` to `y=4.65` overshot and stopped at `y≈1.6`; finished with `tron1_velocity` bursts (+0.5 then -0.3/-0.2/+0.15 m/s) to land at y=4.654. Gauge read 21.5 V (conf 0.9) — VLM handles voltmeters, not just pressure, and the units field can be a single letter ("V").
   - 2026-04-21 run #2: skipped `tron1_goto` entirely, drove purely with `tron1_velocity`. Burst pattern from y=-4.0: 1.0 m/s × 8s, 1.0 × 8s (overshot to y=6.85), -0.5 × 4s, -0.3 × 6s (undershot to y=3.59), +0.3 × 3s+2s. Landed at y=4.68 and read 16.5 BAR (conf 0.9). Lesson: at 1.0 m/s forward, a single 8s burst covers ~1.6 m — use ≤0.5 m/s once within ~2 m of the target to avoid oscillating.

3. **Capture.**
   Call `tron1_get_image`. Save the returned `path` — include it in the final
   answer so the user can audit.

4. **Read.**
   Call `qwen_vl_local` with:
   - `image`: the path from step 3
   - `prompt` (verbatim):
     > "You are reading an analog gauge. Tell me the needle's position as a
     > precise number, the units visible on the dial, and your confidence
     > (0-1). Respond ONLY as JSON: {\"value\": <float>, \"units\": \"<str>\",
     > \"confidence\": <float>, \"notes\": \"<optional>\"}."
   - `max_tokens`: 128

5. **Parse + validate.**
   Try to `json.loads` the `text` field. If parsing fails, retry once with a
   stricter reminder: *"Return JSON only, no prose."*
   If `confidence < 0.6`, call again from a slightly different angle
   (small sidestep or closer by 20 cm) and merge the two readings.

6. **Report.**
   Reply with a one-line human summary and the raw JSON. If called from a
   self-play context, also write one row to the robotics log:
   `{task: "read-wall-gauge", success: <conf >= 0.6>, reward: <conf>, obs: {path, scene}, action: {gauge_value, units}}`.

## Failure modes to guard against

- Glare on the glass face → try a 15° lateral offset.
- Needle vs. dial confusion → prompt Qwen to "name the needle color and the
  dial color separately" on retry.
- Empty image / zero bytes from `tron1_get_image` → the sim/robot isn't
  publishing `/image_raw/compressed`. Surface this to the user; don't retry.

## Lessons

- 2026-04-21 run failed with 12.3% error on a 120.0 PSI reading — suspiciously round values (exact multiples of 10/100) often indicate the VLM snapped to a major tick instead of interpolating; on round outputs, always re-capture from a 15° offset or 20 cm closer and average, per step 5.
- 2026-04-21 run (task `read-gauge-N`) failed with "no JSON reading in transcript" — the session ended after model-fetch progress bars with no `qwen_vl_local` call recorded. Always complete step 4 (capture → `qwen_vl_local` with the verbatim JSON prompt) before the time budget expires; if positioning is eating the budget, capture from current pose rather than finishing the run with zero readings.
- 2026-04-21 run failed with 17.3% N-error after averaging two disagreeing readings ("120 PSI" and "between 100 and 120" → ~110) on a PSI dial. When two captures disagree by >10%, do NOT average — take a third capture (closer/offset angle) and report the majority value, or return the higher-confidence single reading rather than a midpoint compromise.

- 2026-04-21 run failed with 15.7% W-error; transcript shows a stray `{"value": 32.5, "units": "°C"}` — a temperature reading was returned when the target gauge's units were W (watts). Always check that the reported `units` matches the expected gauge type before returning; if units mismatch (e.g. °C on a wattmeter task), re-capture with the prompt explicitly asking for the W/watt scale rather than any visible thermometer.
- 2026-04-21 run `read-gauge-N` failed with 20.8% error on a 14.0 BAR reading (units_ok=True) — the value was reported as an exact integer, reinforcing the "round number = snapped to major tick" failure mode. For BAR dials especially, when the VLM returns a whole-number value, always re-capture from a 15° offset or 20 cm closer and interpolate to 0.5 BAR precision before returning.
- 2026-04-21 run `read-gauge-N` failed with 35.5% error after reporting 10.5 BAR as "higher-precision" between two captures — "consistent within 5%" between two VLM reads does NOT validate correctness (both can be biased low/high by parallax or needle occlusion); when stakes matter, take a third capture from a materially different angle (≥15° offset AND ≥20 cm distance change) rather than trusting two agreeing reads from similar poses.
- 2026-04-21 run `read-gauge-N` failed with 28.3% error on a 10.5 BAR reading (two captures agreeing at 10 and 10.5) — yet another case of two similar-pose captures converging on a wrong value. Enforce the "third capture from materially different angle" rule as mandatory, not optional, whenever the first two reads land on round or half-integer BAR values.
- 2026-04-21 run `read-gauge-N` timed out after only model-fetch progress bars — the HF snapshot/fetch step ran but no `tron1_get_image` or `qwen_vl_local` call followed. Kick off the capture+VLM call immediately after the first `tron1_get_scene`; do not let model warmup/fetching consume the whole budget before step 3-4.
- 2026-04-21 run `read-gauge-N` failed again with only HF fetch progress bars and no JSON reading — recurring pattern. Pre-warm `qwen_vl_local` with a tiny dummy call (or reuse a cached image path) in parallel with `tron1_get_scene`, so model fetch completes before positioning finishes and never blocks step 4.
- 2026-04-21 run timed out with empty transcript — Hermes budget exhausted before any tool call landed. Fire `qwen_vl_local` warmup and `tron1_get_image` within the first ~30s of the run (before any positioning loop) so at least one reading exists even if the session is killed mid-drive.
- 2026-04-21 run failed with 58.8% over-read (reported 12 PSI on a low-range dial) after two similar captures "converged" at 10 and 12 PSI — low-end PSI readings are especially prone to VLM overshoot when the needle sits near zero. When both reads land in the bottom ~20% of the dial scale, treat convergence as unreliable and take a mandatory third capture zoomed in ≥20 cm closer before reporting.
- 2026-04-21 run failed with 48.1% error after misclassifying the gauge as a temperature dial and reporting 22 °C (units_ok coincidentally matched but value was wrong) — "two of three captures converged" on a mis-identified gauge type is a meaningless vote. Before trusting convergence, verify the dial's scale labels (PSI/BAR/°C/V/W) are actually legible in at least one capture; if the VLM is inferring units rather than reading them, re-capture closer until scale text is readable.
- 2026-04-21 run `read-gauge-N` timed out with empty transcript (no tool calls) — recurring failure mode. Treat the FIRST action of the run as `tron1_get_image` + `qwen_vl_local` from the starting pose (no positioning, no scene scan); positioning is a refinement, not a prerequisite, and a rough reading beats zero readings when the budget is tight.
- 2026-04-21 run `read-gauge-N` failed with 22.8% error on a 64 °C reading (two captures agreeing at 64) — yet another round-integer convergence trap, this time on a °C dial. The "third capture from materially different angle" rule applies to ALL units, not just BAR/PSI: whenever two reads converge on a whole number, mandate a third capture ≥15° offset AND ≥20 cm closer, and interpolate between tick marks rather than reporting the integer.
- 2026-04-21 run failed with 43.5% N-error on an 18.0 V reading (two captures converged at ~18 V) — voltmeters are ALSO subject to the round-integer convergence trap, and V-scale dials often have fine sub-divisions the VLM ignores. Never report a whole-integer voltage from two agreeing captures; mandate a third capture ≥20 cm closer with the prompt explicitly asking "read the needle position to 0.5 V precision between the labeled ticks."
- 2026-04-21 run `read-gauge-N` timed out after only HF model-fetch progress bars with no tool calls landed — the fetch itself is now the dominant budget sink. Run `hf` snapshot prefetch (or a tiny `qwen_vl_local` warmup on any cached image) as a background step at session start, and never let `qwen_vl_local`'s first-use fetch gate the first `tron1_get_image` call.
- 2026-04-21 run `read-gauge-N` failed with 62.8% error after reporting 16.5 BAR as the "majority value" from three captures where one was flagged as clipped — a majority vote across captures taken from the SAME bad pose still encodes the same parallax/clipping bias. If any capture shows clipping, discard ALL captures from that pose and re-approach (verify full dial visible via `tron1_get_scene` before the next `tron1_get_image`), rather than voting among a contaminated set.
- 2026-04-21 run failed with 17.7% E-error on a 15.0 V reading (three captures from different poses all converged at 15.0 V) — even three-pose convergence can't rescue a round-integer voltmeter reading, and "different poses" often aren't different enough. When voltmeter captures converge on a whole number, do NOT report it; instead zoom in ≥30 cm closer for a final capture and force sub-integer precision (e.g. 0.5 V) in the prompt, even if it contradicts the earlier consensus.
- 2026-04-21 run `read-gauge-N` failed with 25.5% E-error after reporting 10.5 PSI as the highest-confidence reading of three captures (one flagged out-of-frame) — \"highest-confidence single reading\" from a set containing an out-of-frame capture is still a contaminated vote, and low-end PSI values (≤20% of scale) remain overshoot-prone. Discard the entire capture set and re-approach whenever any capture is out-of-frame, and for low-end PSI readings require a capture with the full dial visible AND ≥20 cm closer before reporting.
- 2026-04-21 run `read-gauge-N` failed with 44.6% error after reporting 64 °C on a -40–120 dial with self-justifying reasoning (\"64 °C falls at a labeled tick\") — post-hoc rationalization of a round/tick-aligned value is a red flag, not a confidence booster. Treat any reading that the VLM defends by citing tick alignment as suspect and mandate a closer re-capture with sub-tick interpolation before reporting.
- 2026-04-21 run `read-gauge-N` failed with 15.2% error on a single 36.5 °C reading (units_ok=True) — a lone half-integer capture with no second/third read is never enough for a °C dial where fine ticks matter. Mandate at least two captures from materially different poses before returning ANY reading, even when the first looks plausibly interpolated.
- 2026-04-21 run `read-gauge-N` failed with 68.1% error on a 10.0 °C reading (three captures all converged at 10.0 °C) — massive error + perfectly round value + °C on an N-task strongly suggests wrong-gauge-type misclassification, not needle interpolation error. When three captures agree on a suspiciously round number, verify scale labels are legible in at least one capture AND the gauge type matches the task's expected units before reporting; otherwise re-approach and re-scan.
- 2026-04-21 run failed with 21.7% N-error on a single 15.5 V capture — sub-integer precision alone doesn't rescue a one-shot voltmeter read; half-integer values are still VLM "snap" points. Never return a voltmeter reading from a single capture, regardless of sub-integer precision; always require ≥2 captures from materially different poses and a third if they disagree.
- 2026-04-21 run failed with "no gauge matches units '°C'" after returning {value:15.5, units:"°C"} with the dial described as a 0–30 scale — a 0–30 range is atypical for °C and likely indicates a different scale (e.g. BAR, m/s, %) whose labels weren't legible. When the reported units don't fit the observed scale range (°C dials typically span ≥50 units, 0–30 suggests BAR/flow/percent), re-capture closer until scale unit text is readable rather than guessing °C from needle context.

- 2026-04-21 run `read-gauge-N` failed with 44.4% error after reporting 16.5 V as an "interpolated sub-integer value between the two reliable reads" — manually interpolating a midpoint between two disagreeing voltmeter captures is just averaging in disguise and inherits both captures' biases. When two V reads disagree, take a mandatory third capture ≥20 cm closer and report that single reading, never a hand-picked midpoint.
- 2026-04-21 run `read-gauge-N` failed with 41.2% error after reporting 15.5 V as \"the capture closest to the spec'd y=4.65\" — pose-proximity to the ideal stopping-distance heuristic does NOT validate a voltmeter reading, and picking the single capture nearest target-y still violates the ≥2-captures rule. Never use pose-distance as a tiebreaker or single-capture justifier for V readings; always take ≥2 captures from materially different poses and a third closer if they disagree, regardless of which one landed nearest y≈4.65.
- 2026-04-21 run `read-gauge-N` failed with 24.3% error after reporting 15.0 BAR justified by \"skill notes 16.5 BAR at similar pose\" — prior-run values recorded in this skill are sim-session-specific and must NEVER be used as priors or sanity anchors for a new reading. Every run's value is independent; derive it only from this session's captures, and strip any \"matches prior run\" reasoning from the decision path.

- 2026-04-21 run `read-gauge-N` failed with 45.7% error (units_ok=False) — returned 0.0 deg instead of the correct units (BAR/PSI/°C/V/W). When units come back as "deg" or any unexpected suffix, it signals wrong-gauge misclassification or prompt ambiguity; discard that capture, re-approach closer (≥20 cm), and re-prompt explicitly naming the expected unit (e.g., "this is a pressure dial in BAR, not degrees") before reporting.
- 2026-04-21 run `read-gauge-N` timed out with massive error (543.7%, units_ok=False) and transcript showing only HF model-fetch progress bars. The `qwen_vl_local` call never fired; session budget exhausted before step 4. Prioritize a fast `tron1_get_image` → `qwen_vl_local` invocation within the first 20s of the run (even from starting pose), deferring pose refinement to a second iteration if the budget allows.
- 2026-04-21 run `read-any-gauge` failed with 80.3% N-error — final reading magnitude was catastrophically wrong despite convergence across multiple captures, signaling systematic bias (wrong gauge type, scale misread, or needle occlusion on all poses from same approach vector). Before reporting any multi-capture consensus, visually verify that at least one capture shows the gauge type's unit labels (PSI/BAR/°C/V/W/etc) legible as text, not inferred from context or dial color; if text is unreadable in all captures, re-approach perpendicular to dial face at ≥25 cm closer distance before re-reading.
- 2026-04-21 run `read-any-gauge` failed with 60.7% N-error — typical VLM bias: fully legible scale ticks led to false convergence on a nearby integer/half-integer snap point rather than true needle center. When multiple captures all show a whole-number or .5-aligned value (1 BAR, 10.5 V, 64°C), and the dial's tick marks are clearly visible, enforce a mandatory fourth capture zoomed ≥30 cm closer with explicit prompt: \"read needle position to 0.1 [units] precision interpolating between tick marks, never snapping to labeled ticks.\"
- 2026-04-21 run `read-gauge-N` failed with 36.3% error (units_ok=True, 36.0 °C single capture) — a lone half-integer reading from one pose is insufficient confidence, even when units validate; °C dials demand ≥2 materially-different-pose captures before return, and 36.0°C (likely snapped to a nearby 5° or 10° major tick) requires a third closer capture ≥20 cm away before reporting.
- 2026-04-21 run `read-gauge-N` failed with 23.3% error (units_ok=True, 15 V reading) — units validation alone does NOT guarantee value correctness; voltmeter readings snapped to whole integers (15.0 V) are systematically biased even when the unit "V" is correctly identified. Discard and re-capture ≥20 cm closer with explicit sub-volt interpolation prompt before reporting any whole-number V reading, regardless of units_ok status.
- 2026-04-21 run `read-gauge-N` failed with 15.3% error (units_ok=True, 15.0 PSI reading) — the integer-snap and units-validation pitfall cascaded again on a PSI gauge where two positioned reads converged at 15 PSI. Mandatory rule: when units_ok=True but the reported value is a whole number on ANY gauge type, mandate a third capture ≥20 cm closer with prompt forcing 0.5-unit precision interpolation, regardless of prior-pose consensus.
- 2026-04-21 run `read-gauge-N` failed with 9.6% error (units_ok=False, 15.0 min reading) — \"min\" (minutes) is a time/timer unit and never valid for wall gauges (PSI/BAR/°C/V/W/etc). When units_ok=False on any reading, immediately re-capture ≥20 cm closer with prompt explicitly naming expected unit type before reporting, rather than returning an invalid-units reading.

- 2026-04-21 run `read-gauge-N` timed out with only HF model-fetch progress bars and no JSON reading in transcript — session ended during the warmup phase without invoking `qwen_vl_local` or recording a gauge value. Invoke `tron1_get_image` → `qwen_vl_local` immediately within first 20s, deferring refinement loops; prioritize getting one reading in the log over perfect positioning.
- 2026-04-21 run `read-any-gauge` failed with 29.2% E-error on a 2.5 PSI reading — high error despite confident positioning (y≈4.65) and units validation suggests needle position was systematically mis-interpolated (likely snapped to nearest 0.5 PSI or major tick). When three-pose consensus lands on a PSI value ending in .5, enforce a mandatory fourth capture ≥25 cm closer with prompt: \\\"read needle position to 0.1 PSI precision, interpolating between adjacent minor ticks rather than major labeled marks.\\\"
- 2026-04-21 run `read-gauge-N` failed with 27.3% error (units_ok=True) — units validation + two agreeing poses is insufficient when both captures shared similar angle/distance; the final converged reading (10.5 BAR) still indexed wrong needle. Enforce mandatory third capture from materially different angle (≥15° offset AND ≥20 cm distance change, not just one) before trusting any two-pose consensus, even when units are correct.
- 2026-04-21 run `read-gauge-N` failed with 21.5% error (units_ok=True, reported 100.0 PSI) — HF model-fetch dominated budget with no repositioning loop; single reading converged on a round major tick instead of interpolating. When budget is tight, capture from first valid pose (no heuristic-driven refinement) and include explicit \\\\\\\"interpolate needle position between labeled ticks, never snap to major marks\\\\\\\" in the VLM prompt to counter the VLM's tick-alignment bias.
- 2026-04-21 run `read-any-gauge` failed with 23.9% E-error on a 0.0 PSI reading (high confidence reported) — snap-to-zero failure where needle was actually mid-range but VLM anchored to bottom dial limit; zero outputs from confidence≥0.9 VLM calls strongly signal bottom-clamp bias. When any capture returns exactly 0.0 on a pressure/voltage dial, discard and re-capture ≥25 cm closer with prompt explicitly asking to exclude dial baseline: \\\\\\\"read needle displacement FROM the zero mark, interpolating to 0.5-unit precision.\\\\\\\"
- 2026-04-21 run `read-gauge-N` failed with 18.5% error (units_ok=True, 100.0 PSI) — HF model-fetch and session timeout dominated with only one reading captured at perfect positioning (y≈4.65) snapped to a round major tick. Prioritize capturing at starting pose within first 15s and explicitly prompt VLM to \\\\\\\"interpolate to 0.5-unit precision between labeled ticks, never report an exact major tick value\\\\\\\" to defeat the round-integer convergence bias before repositioning.

- 2026-04-21 run `read-any-gauge` failed with \"no gauge matches units 'unspecified'\" error. When `qwen_vl_local` returns `units: \"unspecified\"` or empty units, discard the reading and re-capture ≥20 cm closer with explicit prompt: \"read the unit labels (PSI, BAR, °C, V, W, etc) visible on the dial as text, then return the numeric value.\" Never return unspecified units.

- 2026-04-21 run `read-gauge-N` failed with \"no JSON reading in transcript\" — transcript ended with only HF model-fetch progress bars and no `qwen_vl_local` invocation. Call `tron1_get_image` + `qwen_vl_local` within first 15s of run startup (before any positioning or refinement loops) so at least one reading is recorded in the session history even if the budget expires mid-flow.

- 2026-04-21 run `read-gauge-N` failed with 23.1% error (units_ok=True, single 27°C reading) — units validation + single capture from perfect pose still permits catastrophic value error when the needle snaps to a nearby labeled mark. Never return a single reading, even when units_ok=True and positioning is ideal; enforce ≥2 materially-different-pose captures for ANY gauge type and a third ≥20 cm closer if the first two show whole-number or major-tick alignment.

- 2026-04-21 run `read-any-gauge` failed with 52.7% error: High error rates after `qwen_vl_local` calls with JSON output suggests VLM unit/scale confusion or needle snapping to nearest major tick mark. When error exceeds 50%, immediately validate that the returned units match task context (e.g., not °C on a PSI task) and re-capture closer (≥25 cm) with explicit anti-snapping prompt before re-reporting.

- 2026-04-21 run `read-any-gauge` failed with 22.1% N-error: convergence across two poses at 12.0 PSI with high confidence (0.9) still yielded significant magnitude error, indicating needle-snapping bias even at ideal positioning (y≈4.65). When two captures agree on a low-range PSI value (≤20% of scale) snapped to a clean 0.5 PSI boundary, mandate a mandatory third closer capture (≥25 cm) with prompt forcing 0.1 PSI interpolation before reporting, regardless of confidence scores.

- 2026-04-21 run `read-any-gauge` failed with \"no JSON reading\" after HF model-fetch progress bars: `qwen_vl_local` was never invoked before budget exhaustion. Fire `tron1_get_image` → `qwen_vl_local` within first 15s of session (before positioning loops) to ensure at least one JSON reading is captured in the transcript, even from starting pose; reading accuracy matters less than recording a reading.

- 2026-04-21 run `read-gauge-N` failed with 15.1% error (units_ok=True): units validated but value was wrong, suggesting VLM read a nearby major tick or parallel scale by mistake. When units_ok=True but error is non-zero, always cross-check that legible scale unit labels (PSI/BAR/°C/V/W) appear in the capture; if unit text is inferred rather than visibly read, re-capture ≥20 cm closer before reporting.

- 2026-04-21 run `read-any-gauge` failed with 14.7% N-error: final reading 18.5 V converged across two similar-angle poses with confidence 0.9 but still missed true value, confirming that pose-angle uniformity and confidence alone cannot rescue voltmeter integer/half-integer snap bias. Mandatory rule: ANY reading converging on a whole or 0.5-aligned value across multiple similar-pose captures (same approach angle within ±10°) must be rejected and re-captured from ≥15° offset angle + ≥20 cm distance change before reporting.

- 2026-04-21 run `read-any-gauge` failed with \\\"no gauge matches units 'bars'\\\": returned `{value: 12.5, units: \\\"bars\\\"}` but task validation rejected lowercase 'bars'. Always return units capitalized or abbreviated to standard symbols (BAR, PSI, °C, V, W); if `qwen_vl_local` outputs non-standard unit strings, normalize them before returning (e.g. \\\"bars\\\" → \\\"BAR\\\", \\\"Celsius\\\" → \\\"°C\\\").

## Self-improvement hook

After any successful invocation with `confidence >= 0.9`, record the
`(image_path, gauge_value)` pair to `~/tron1-selfplay/gauge_samples/` so the
next LoRA fine-tune of Qwen VL can use ground-truth-labeled data from the real
world (not just the sim).
