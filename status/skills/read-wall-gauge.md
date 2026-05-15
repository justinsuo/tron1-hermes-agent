---
title: Read Wall Gauge
name: read-wall-gauge
description: Read the value and units from a wall-mounted gauge using the Tron 1 camera and Qwen-VL model.
---
## Read Wall Gauge

### Description
Read the value and units from a wall-mounted gauge using the Tron 1 camera and Qwen-VL model.

### Steps
1. Drive the robot to the wall gauge location (y ≈ 4.65).
2. Capture an image of the wall gauge using `tron1_get_image`.
3. Use `qwen_vl_local` to analyze the image and read the gauge.

## Failure notes
- Avoid using 'read_any_gauge' for pressure gauges; use 'read_pressure_gauge' instead to prevent JSON reading errors.
- JSON parsing errors may occur if the gauge image lacks clear markings; ensure images are high-resolution and well-lit for accurate readings.- JSON parsing errors may occur if the gauge image lacks clear markings; ensure images are high-resolution and properly labeled.
- When units are not recognized (e.g., 'hours'), the gauge reading may fail. Ensure units are explicitly defined in the input data.
- JSON parsing errors may occur if the gauge image lacks clear markings; ensure images are high-resolution and well-lit for accurate readings.- JSON parsing errors may occur if the gauge image lacks clear markings; ensure images are high-resolution and properly labeled.
## Lessons
- Ensure the transcript contains valid JSON for parsing. If the transcript is empty or malformed, the gauge reading cannot be extracted.- Ensure the transcript is properly formatted as JSON to avoid parsing errors during gauge value extraction.
- When reading wall gauges, ensure the 'units' field is explicitly specified in the output metadata to avoid unit ambiguity.
ion
Ensure the robot is at the correct location and the image is clear.

### Notes
- This skill requires the robot to be at the correct location.
- The image must be clear for accurate reading.
- The gauge must be a wall-mounted gauge.

### Example
```bash
tron1_goto x=0 y=4.65
tron1_get_image
qwen_vl_local image_path='path_to_image' prompt='What does the wall gauge at world y=+5.85 read in numerical value and units?'
```