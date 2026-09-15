# Output sharpness

The main menu's Sharpness slider controls a spatial GPU filter after neural
rendering and SR/DLAA, before HDR reconstruction, frame generation and export.
It does not change the resolution or the existing SR/DLAA behavior.

Start around 50%; 0% disables the pass completely (no allocation, copy or
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
