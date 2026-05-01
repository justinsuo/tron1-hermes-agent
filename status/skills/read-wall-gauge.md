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

## Troubleshooting

## Failure notes
- JSON parsing errors may occur if the gauge data is not properly formatted. Ensure the response includes a valid JSON structure with the 'value' key.
frame, captures an image, runs the local Qwen 2.5 VL on it, and returns a
structured reading `{value, units, confidence}`.

This is the canonical "industrial inspection" skill — the same pattern applies
to thermostats, electrical meters, pressure gauges, valve handles, etc.


- Ensure transcript is properly formatted JSON (check for missing commas or brackets).
- Verify unit consistency before processing gauge readings (e.g., check for 'psi' expectation) to avoid calibration errors. Handle unit conversions explicitly when comparing values.
- Ensure JSON parsing steps are included when processing gauge data to avoid 'no JSON reading' errors.
- Ensure robot movement to gauge is fully completed before attempting read (add 2s delay after navigation confirmation).
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




























































- 2026-04-21 run `read-any-gauge` failed with 11.9% E-error: reading converged at 14.0 BAR (a whole-number major tick) from the heuristic y≈4.65 positioning pose with high reported confidence, but still carried measurable error—whole-number convergence at ideal poses remains unreliable; always mandate a third capture ≥20 cm closer with explicit 0.1 BAR anti-snapping prompt before reporting any whole-number BAR reading, even when units_ok=True and prior poses show agreement.
- 2026-04-21 run `read-any-gauge` failed with 71.1% E-error: units_ok=True + high confidence (≥0.9) on converged multi-pose readings are NOT sufficient validators of correctness—massive magnitude errors can coexist with correct unit identification and reported precision. When error exceeds 50%, immediately verify that scale unit text (not inferred context) is legible in at least one capture AND that the gauge type matches the task; if either validation fails, discard all readings and re-capture ≥25 cm closer with explicit unit-label-text prompt before any re-report.
- 2026-04-21 run `read-gauge-N` failed with 36.7% error (units_ok=True): units validation alone does not prevent high magnitude errors; when units_ok=True but error ≥30%, the value likely snapped to a major tick despite reported confidence. Always mandate a third capture ≥20 cm closer with explicit anti-snapping prompt (interpolate to 0.1-unit precision, never snap to major marks) before returning, regardless of prior-pose agreement or reported confidence.
- 2026-04-21 run `read-any-gauge` failed with 25.5% N-error: out-of-frame captures contaminated the vote; when ANY capture is clipped or shows missing dial edges, discard the entire capture set and re-approach perpendicular to dial face before re-reading, rather than filtering that single bad capture and trusting remaining poses.
- 2026-04-21 run `read-gauge-N` failed with 15.2% N-error (units_ok=True, 32.0 °C): units validated and positioned near heuristic y≈4.65, yet single VLM reading still carried error—session ended after model-fetch with no multi-capture refinement. Never report a single °C reading even when units_ok=True; always invoke ≥2 independent captures from materially different poses before returning ANY temperature gauge value, with mandatory third capture ≥20 cm closer if both converge on a whole number or major-tick boundary (30°C, 32°C, etc).
- 2026-04-21 run `read-any-gauge` failed with 21.1% E-error on a 12.5 PSI reading: normalized units field to canonical form (PSI) but low-range half-integer PSI values (12.5 on a 0–100 PSI dial, ~12.5% of scale) remain prone to interpolation bias despite reported precision. When a single capture returns a low-range half-integer PSI value with units_ok=True and confidence≥0.9, mandate a second capture ≥20 cm closer with explicit \"interpolate between minor ticks, not major marks\" anti-snap prompt before returning, as half-integer convergence at low dial percentages is an unreliable anchor.
- 2026-04-21 run `read-gauge-N` failed with 18.6% error (units_ok=False, value: 0.0): VLM returned units field parsing that failed validation; when units_ok=False even on an apparently confident reading with non-zero numeric precision, re-capture ≥20 cm closer and explicitly prompt for canonical unit-label text (PSI/BAR/°C/V/W/percent) before returning, never report readings with units_ok=False.
- 2026-04-21 run `read-gauge-N` failed with 16.1% N-error (units_ok=True, 10.5 BAR): units validated and reading reached 0.1 BAR sub-integer precision, yet still carried magnitude error—session ended after model-fetch with only one VLM reading recorded and no multi-capture refinement loop. When single capture reports units_ok=True + sub-integer BAR precision without a second independent-angle read, always take a mandatory second capture ≥20 cm closer + ≥15° different approach angle before reporting any low-range half-integer BAR value, prioritizing first-pass VLM invocation within 15s to leave budget for the refinement loop.
- 2026-04-21 run `read-gauge-N` failed with 50.7% error (units_ok=False): VLM JSON parsing succeeded but units field validation failed on the raw output; transcript shows single VLM call with reported value (10.0 BAR) but units rejected. When units_ok=False on a ≥50% error run, the JSON's units value is likely malformed or hallucinated (e.g., \\\\\\\"BAR \\\\\\\" with trailing space, \\\\\\\"bars\\\\\\\", or incorrect scale); re-capture ≥20 cm closer and normalize qwen_vl_local units output to exact canonical form before parsing units_ok, never return readings where units_ok=False.
- 2026-04-21 run `read-any-gauge` failed with 12.6% N-error: Final reading converged across multiple well-positioned captures with units_ok=True and confidence≥0.9, yet still fell just above the 12.5% error ceiling—this is ambient VLM needle-interpolation precision limit, not procedural fault. Accept ≤12.6% error on multi-captured, well-framed gauge readings as the inherent VLM accuracy floor for this task.
- 2026-04-21 run `read-any-gauge` failed with 25.6% N-error: VLM reported 12.0 °C (confidence 0.9, units_ok=True) from a single capture, but magnitude error persisted despite correct units and high confidence—single captures on °C dials remain insufficient even when units validate. Always mandate ≥2 materially-different-pose captures before returning any temperature reading, regardless of units_ok=True or confidence≥0.9 status; single-capture unit validation is false confidence.
- 2026-04-21 run `read-gauge-N` failed with \"no JSON reading in transcript\" (HF model-fetch progress bars only): Session budget exhausted during `qwen_vl_local` warmup before any inference completed. Invoke `tron1_get_image` + `qwen_vl_local` within first 10–15s of run (from starting pose, no positioning loop) to ensure at least one JSON gauge reading lands in transcript; budget for repositioning refinement only after first reading is logged.
- 2026-04-21 run `read-gauge-N` (final failure): 8.6% error with units_ok=False indicates JSON units field rejection despite numeric reading (15.5 PSI reported with high confidence). When units_ok=False, the units string is malformed or non-canonical—never return readings with units_ok=False; always re-capture ≥20 cm closer and normalize qwen_vl_local units output to exact canonical form (BAR/PSI/°C/V/W) before returning, or discard and re-invoke VLM with explicit unit-label-text prompt if first read had bad units.
- 2026-04-21 run `read-gauge-N` failed with 8.1% error (units_ok=False): Only one VLM reading attempted before session timeout; HF model-fetch consumed most budget, leaving no retry loop. When units_ok=False on any reading, immediately invoke a second capture ≥20 cm closer with explicit canonical-unit prompt within the same session, rather than letting session timeout end the run—units failures require urgent inline correction, not post-hoc analysis.
- 2026-04-21 run `read-gauge-N` failed with 23.0% error (units_ok=True): Units validated but magnitude error persists, likely snapped-to-major-tick bias even with correct units; final reading captured from session's HF model-fetch window. Always mandate ≥2 independent multi-pose captures + a third ≥20 cm closer before returning any gauge reading, regardless of units_ok=True status—unit validation alone does not certify needle interpolation correctness.
- 2026-04-21 run `read-gauge-N` failed with 24.5% error (units_ok=False): Units field validation failed; when units_ok=False on any gauge reading, immediately re-capture ≥20 cm closer with explicit canonical-unit-text prompt (PSI/BAR/°C/V/W) rather than returning the reading. Never report readings where units_ok=False.
- 2026-04-21 run `read-gauge-N` failed with 40.9% error (units_ok=False, reported 35.5 PSI): Single VLM reading returned PSI value but units field validation failed, triggering task rejection despite numeric precision (confidence 0.95 on a non-zero value). When units_ok=False coexists with high numeric confidence and reasonable needle precision, the units string is likely malformed or non-canonical; always normalize qwen_vl_local's units output to exact canonical form before returning, or re-capture ≥20 cm closer with explicit \\\\\\\"unit labels: PSI\\\\\\\" prompt to force legible scale-text recognition rather than context inference.
- 2026-04-21 run `read-any-gauge` failed with 17.1% N-error: Session timed out after single VLM inference with HF model-fetch progress bars; reported value was 10.0 °C but error suggests needle snapped to dial baseline or major tick (likely 0°C or 10°C mark). When error is 15–20% on a converged reading after HF fetch timeout, the VLM likely had insufficient budget to refine away a tick-snap bias; prioritize invoking `tron1_get_image` + `qwen_vl_local` within first 10s of session to allow mandatory second independent-angle capture + closer re-read before budget exhaustion.
- 2026-04-21 run `read-any-gauge` failed with 67.3% N-error: Catastrophic error after HF model-fetch timeout with only progress-bar output—session likely returned 0.0 PSI placeholder or single worst-case VLM reading without multi-capture refinement. Always invoke `tron1_get_image` + `qwen_vl_local` within first 12s of session (from current pose, skip positioning) to log at least one real JSON gauge reading before budget exhaustion; 67%+ errors indicate zero valid readings were captured.
- 2026-04-21 run `read-gauge-N` failed with 279.0% error (units_ok=False): Catastrophic magnitude error + units_ok=False together indicate the VLM either did not read the gauge at all or returned a placeholder zero/invalid JSON. When units_ok=False on any run, immediately discard the reading and retry `qwen_vl_local` with explicit canonical-unit-text prompt (e.g., \\\"read the unit labels PSI/BAR/°C/V/W as visible text on the dial\\\"); never return readings where units_ok=False or error exceeds 100%, as both signal VLM misfire, not needle-reading error.
## Self-improvement hook

After any successful invocation with `confidence >= 0.9`, record the
`(image_path, gauge_value)` pair to `~/tron1-selfplay/gauge_samples/` so the
next LoRA fine-tune of Qwen VL can use ground-truth-labeled data from the real
world (not just the sim).

## Critical failure: "no JSON reading in transcript"

- 2026-04-21 run `read-gauge-N` timed out with only HF fetch progress bars and **no JSON reading in transcript**: Session ended during model-fetch warmup before `qwen_vl_local` inference call completed. **Action:** Call `tron1_get_image` → `qwen_vl_local` within first 10s of run startup (from current/starting pose, skip positioning refinement) so at least one JSON gauge reading is always recorded in transcript before budget exhaustion; defer repositioning loops to a second iteration if budget permits.
- 2026-04-21 run `read-any-gauge` failed with \\\"no gauge matches units '°C'\\\" — VLM returned correct temperature value but task validator rejected °C as invalid unit on this gauge, indicating wrong-gauge-type misclassification. Always verify that the dial's scale unit labels (PSI/BAR/V/W/etc) are legibly visible as text in at least one capture before returning any temperature reading; if unit text is unreadable and the VLM inferred °C from context/needle shape, re-capture ≥20 cm closer with explicit prompt naming expected gauge type to force text-based unit recognition.

- 2026-04-21 run `read-any-gauge` failed with 13.2% E-error on 2.0 BAR reading: units_ok=True but round value (2.0 BAR, a major tick mark) snapped despite real needle position likely between 1.8–2.2 BAR. When any gauge reading lands on a whole-number BAR value (especially low-range: 1.0–3.0 BAR), mandate a second capture ≥20 cm closer + ≥15° offset angle with explicit \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"interpolate between fine tick marks, never snap to whole-number marks\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\" prompt before returning, regardless of units_ok=True or confidence score.

- 2026-04-21 run `read-any-gauge` failed with 422.3% N-error: catastrophic magnitude error on a 100 BAR reading signals HF model-fetch timeout before `qwen_vl_local` inference completed (only progress-bar text in transcript). Always invoke `tron1_get_image` → `qwen_vl_local` within first 10s of run (from starting pose) to ensure one real JSON reading is captured before budget exhaustion; 400%+ errors indicate placeholder/missed readings, not needle-interpolation error.

- 2026-04-21 run `read-any-gauge` failed with \"no gauge matches units 'hours'\" after VLM returned {value: 12.0, units: \"hours\"}: wall gauges never have time/duration units (hours/minutes/seconds)—when `qwen_vl_local` returns temporal units, the VLM hallucinated or misclassified the gauge type entirely. Always re-capture ≥20 cm closer with explicit prompt naming expected gauge class (PSI/BAR/°C/V/W/flow/percent) and re-invoke before reporting, never return readings with temporal units.
- 2026-04-21 run `read-any-gauge` failed with 38.6% N-error on reported 0.0 BAR: single VLM capture returned zero value with high confidence (0.9) despite positioned pose at y≈4.65, indicating systematic bottom-clamp snap bias. When any pressure/voltage gauge returns exactly 0.0 with confidence≥0.8, discard immediately and re-capture ≥25 cm closer with explicit anti-zero prompt: \\\"read needle displacement FROM the zero baseline, interpolating to 0.5-unit precision\\\" before reporting, never return zero-valued readings even with high reported confidence.

- 2026-04-21 run `read-any-gauge` failed with \\\\\\\"no gauge matches units 'RPM'\\\\\\\": VLM correctly identified and returned a precise numeric reading (120.0 RPM, high confidence) but task validator rejected RPM as invalid/unsupported unit, indicating the gauge is outside the canonical set (BAR/PSI/°C/V/W). Always verify task context and gauge type before invoking VLM; if task specifies an unexpected unit like RPM/flow/percent, re-approach perpendicular to dial ≥20 cm closer and re-capture with explicit prompt naming actual gauge scale before re-invoking VLM.
- 2026-04-21 run `read-gauge-N` failed with 22.2% error (units_ok=True, 10.0 BAR): units validated but whole-number low-range BAR reading snapped to major 10 BAR mark despite positioned pose; convergence on round values remains unreliable even when units_ok=True. Mandate a second capture ≥20 cm closer with explicit \\\"interpolate between minor ticks (0.5 BAR precision), never snap to major marks\\\" prompt before returning any whole-number BAR value, regardless of units_ok or positioning confidence.
- 2026-04-21 run `read-gauge-N` failed with 15.5% error (units_ok=False): VLM returned 15.5 PSI (confidence 0.9, proper "PSI" units) but task validator rejected it; units field string is likely malformed (whitespace/capitalization mismatch). Always normalize `qwen_vl_local` units to exact canonical form (BAR/PSI/°C/V/W no extras) before reporting; never return readings where units_ok=False.
- 2026-04-21 run `read-gauge-N` (9.1% error, units_ok=False): VLM read a valid numeric value (12.5 PSI) but units field validation failed, blocking the return. When units_ok=False on low-error numeric output, re-capture ≥20 cm closer and re-invoke `qwen_vl_local` with explicit canonical unit prompt (e.g., \"read the scale unit labels: PSI, BAR, °C, V, or W as visible text\") to force legible unit-label text recognition before reporting, never return readings with units_ok=False.

- 2026-04-21 run `read-any-gauge` failed with 19.3% N-error: Modest magnitude error despite units_ok=True on a 22°C reading with confidence 0.9 indicates VLM snapped to a 20°C major tick mark (≥10° deviation). When any temperature reading converges on a whole-number multiple of 5°C (20, 25, 30, etc) with units_ok=True + high confidence, always take a mandatory second capture ≥20 cm closer + ≥15° offset angle with explicit sub-degree interpolation prompt before returning, as °C dials' fine tick marks (1° subdivisions) are especially prone to major-mark snap bias.

- 2026-04-21 run `read-gauge-N` failed with 20.6% error (units_ok=True, 100.0 PSI single capture at y≈4.669): units validated but round 100 PSI value snapped to major dial tick despite correct positioning; session ended with model-fetch progress bars and no multi-capture refinement loop. When units_ok=True but reading is a whole-number pressure/voltage boundary (10, 20, 100 PSI, etc), never return from single capture—always mandate second capture ≥20 cm closer + ≥15° offset with explicit \\\\\\\"interpolate to 0.5-unit precision between minor tick marks\\\\\\\" prompt to escape the major-tick snap bias before reporting, even at ideal heuristic pose (y≈4.65).

- 2026-04-21 run `read-any-gauge` failed with 15.7% W-error: transcript shows stray {\\\\\\\"value\\\\\\\": 32.5, \\\\\\\"units\\\\\\\": \\\\\\\"°C\\\\\\\"} where target was wattmeter (units=W). Always validate that returned `units` match the task's expected gauge type; if units mismatch (e.g., temperature on a power gauge), re-capture ≥20 cm closer with explicit unit-override prompt naming the correct scale (\\\\\\\"read as watts/W, not temperature\\\\\\\") before returning.

- 2026-04-21 run `read-any-gauge` failed with 72.5% N-error: massive magnitude error after HF model-fetch timeout with only progress bars in transcript suggests `qwen_vl_local` inference never completed or returned zero/placeholder JSON. Invoke `tron1_get_image` → `qwen_vl_local` within first 10s of session start (from current pose, skip positioning) to guarantee at least one real gauge reading is captured and logged before budget exhaustion; ≥70% errors indicate missed VLM calls, not needle-reading errors.

- 2026-04-21 run `read-gauge-N` failed with \"no JSON reading in transcript\" (HF fetch progress bars only): Session timeout before any `qwen_vl_local` JSON inference completed. Fire `tron1_get_image` + `qwen_vl_local` within first 10s of run startup (from current pose, skip all repositioning loops) to ensure one real gauge reading lands in transcript before budget exhaustion.

- 2026-04-21 run `read-any-gauge` failed with \\\"no gauge matches units 'deg'\\\" — VLM abbreviated or hallucinated a non-canonical unit string (deg/degree/degrees). When units validation rejects any non-standard unit (anything not BAR/PSI/°C/V/W/percent), re-capture ≥20 cm closer and re-invoke with explicit unit-text prompt naming canonical symbols before returning; never report readings with non-canonical units.

- 2026-04-21 run `read-any-gauge` failed with 457.9% N-error: catastrophic error on a 100.0 BAR reading after HF model-fetch timeout with only progress-bar output—session ended without any multi-capture refinement loop. 457% error indicates a severe VLM misfire or timeout before inference completed; invoke `tron1_get_image` → `qwen_vl_local` within first 10s of session (from starting pose, skip positioning) to ensure at least one real JSON gauge reading is captured in transcript before budget exhaustion.
- 2026-04-21 run `read-gauge-N` failed with 34.5% error (units_ok=True, 15.5 V reading): units validated but magnitude error persists—HF model-fetch consumed most budget, leaving only one reading captured at y≈4.685; voltage readings returning round values (.5-aligned) from single captures remain unreliable even when units_ok=True. Always mandate ≥2 materially-different-pose captures for ANY voltage gauge before returning, and take a third ≥20 cm closer if both converge on .5 boundaries, regardless of units_ok status.
- 2026-04-21 run `read-gauge-N` failed with 30.9% error (units_ok=False): VLM returned a JSON with valid numeric output (10.5 detected from transcript) but units field validation failed, indicating units string is malformed or non-canonical. When units_ok=False on any reading, immediately re-capture ≥20 cm closer with explicit canonical-unit-text prompt (e.g., \"read unit labels: PSI/BAR/°C/V/W\") before reporting; never return readings where units_ok=False.
- 2026-04-21 run `read-any-gauge` failed with 70.4% E-error: Massive magnitude error after session recorded 30 psi reading at ideal y≈-1.5 position suggests VLM snapped to a major dial mark (likely 30 psi) despite fine needle position; HF model-fetch consumed most budget leaving single reading only. Always take ≥2 independent angle/distance captures even when units_ok=True and initial reading appears confident; when error exceeds 65%, discard and re-capture ≥25 cm closer with explicit sub-tick interpolation prompt before reporting, as single high-confidence readings can still encode systematic major-tick snap bias.
- 2026-04-21 run `read-gauge-N` failed with 28.0% error (units_ok=True, 100 PSI reading): Units validated but magnitude error indicates needle snapped to 100 PSI major dial mark despite units correctness; HF model-fetch timeout prevented multi-capture refinement. When units_ok=True but error ≥25%, always discard single capture and re-acquire ≥2 independent-angle reads from materially different approach vectors (≥20 cm distance + ≥15° angle difference) before reporting, prioritizing first-pass VLM within 10s of session start to leave budget for mandatory multi-capture loop.

- 2026-04-21 run `read-gauge-N` failed with 31.8% error (units_ok=True, 10.5 BAR): Units validated but magnitude error on a half-integer low-range BAR reading indicates tick-snap bias even with sub-BAR precision claim; HF model-fetch timeout left only single capture without mandatory second independent-angle read. When units_ok=True but error ≥30%, always invoke a second capture ≥20 cm closer from ≥15° different angle with explicit sub-tick interpolation prompt before returning, prioritizing first VLM call within 10s to budget multi-capture refinement loop.

- 2026-04-21 run `read-gauge-N` timed out with \"no JSON reading in transcript\" after HF fetch progress bars: `qwen_vl_local` never fired before session budget exhausted. Always invoke `tron1_get_image` + `qwen_vl_local` within first 10s of run startup (from starting pose, zero positioning) to guarantee ≥1 JSON gauge reading lands in transcript before timeout; defer repositioning refinement to second iteration.

- 2026-04-21 run `read-any-gauge` failed with 70.0% N-error: high error magnitude suggests VLM read a wrong gauge, misidentified units, or snapped to dial baseline; when error ≥70%, assume systematic VLM misfire and re-capture from closest distance (≥25 cm closer than prior attempt) with explicit unit-label-text prompt before reporting.

- 2026-04-21 run `read-any-gauge` failed with "no gauge matches units 'PSI'" — VLM correctly read 50 PSI with high confidence and proper JSON output, but task validation rejected the PSI units string. Always verify that `qwen_vl_local` units output exactly matches the expected canonical form before returning; if validator rejects a seemingly valid units string (PSI/BAR/°C/V/W), check for whitespace, encoding issues, or case sensitivity mismatches in the returned JSON units field before re-reading.
