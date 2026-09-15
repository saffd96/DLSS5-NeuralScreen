# Output sharpness

The main menu's Sharpness slider appears and runs only with SR/DLAA enabled,
after neural rendering and SR/DLAA, before HDR reconstruction, frame generation and export.
Disabling SR/DLAA disables sharpening but preserves its chosen strength.
It does not change the resolution or the existing SR/DLAA behavior.

The range is 0?100%. Start around 50%; 0% disables the pass completely (no allocation, copy or
dispatch). NR OFF remains an unprocessed bypass. Strength is saved locally.
Changes apply without restarting the worker and force a refresh of static frames.

The filter uses a two-pixel axial neighborhood, a small noise floor and a
bounded high-pass correction. Unlike the previous one-pixel, contrast-gated
experiment, it responds to soft, low-contrast edges. It preserves alpha,
uniform areas and neighborhood color bounds. High settings can emphasize
compression or noise; this improves edge contrast, not missing detail.

Validation:

- `runtime\python.exe tests\test_detail_controls.py`: config, mouse input and wire.
- `runtime\python.exe tests\test_detail_shaders.py`: production shader on WARP,
  including soft edges, monotonic strength, zero identity and color bounds.
- `runtime\python.exe tests\test_detail_pipeline.py --run`: NVIDIA readback,
  comparing matching frames against unsharpened control runs in NR, DLAA and SR.
- `runtime\python.exe tests\test_frame_generation.py --hdr --dynamic --check-pixels --sr --ui --detail`:
  HDR presentation and generated-frame readback at 2x/3x/4x.

## 100% versus 200% comparison (2026-09-16)

RTX 5080, production worker readback, SDR, no FG, NR intensity zero to isolate
sharpening. Separate runs compared matching frame positions, with identical
source, reset flags and warmup; this avoids counting SR initialization drift
as a sharpness difference. Inputs: synthetic soft text (640x360), a blurred
application screenshot (640x720), and a blurred desktop crop (1280x720).
Each was evaluated through native DLAA and 50% SR. Values below measure
difference, not reconstruction quality.

| Input | Mode | Mean absolute channel difference / 255 | Pixels with any channel difference > 2 |
| --- | --- | ---: | ---: |
| Soft text | DLAA | 0.123 | 2.31% |
| Soft text | SR | 0.120 | 2.29% |
| Application UI | DLAA | 0.094 | 1.34% |
| Application UI | SR | 0.083 | 1.18% |
| Desktop | DLAA | 0.196 | 3.72% |
| Desktop | SR | 0.183 | 3.34% |

Across these cases, fewer than 0.7% of pixels differed by more than 8 levels.
Mean differences on detected edges were 0.69–2.15 levels per channel.
Visual inspection of the UI pair showed little readability benefit. The
additional gain mostly reaches the existing neighborhood/correction bounds;
200% is not twice the visible sharpness. The slider was therefore returned
to 0–100%. This is a limited static SDR comparison, not a perceptual study of
all games, videos or HDR content. Existing GPU checks still verify live
SR toggling, exact zero-strength output and a stronger response at 100% than 50%.
