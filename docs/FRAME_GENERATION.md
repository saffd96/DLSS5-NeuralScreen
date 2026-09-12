# Experimental DLSS Frame Generation

Enable **DLSS Frame Generation** on the main menu. A multiplier slider appears
while enabled: ×2, ×3 or ×4 means one, two or three additional frames per real
frame. Both controls are saved in config.json and applied on the next frame,
without restarting Neural Rendering. Changing the multiplier recreates only FG
resources. Turning FG off returns to ordinary output.

`start-framegen.bat` remains a convenient HDR/profiling launcher; the menu and
saved config control FG. `NS_FRAMEGEN=1` is a fallback for older protocol clients
and standalone tests. The application explicitly overrides it from the menu.
`native/nvngx_dlssg.dll` is required in addition to the original NR library.

The path is capture (latched before motion estimation) -> Neural Rendering -> HDR composition (when active) ->
DLSS-G -> paced presentation. With FG enabled, HDR composition writes 10-bit
BT.2020/ST.2084 (HDR10), which is used for both real and generated frames.
DLSS-G does not support FP16 scRGB: passing it through clips highlights and
causes brightness flicker. With FG off, the original FP16 scRGB path remains.
All generated frames and snapshot copies are submitted together, with a single
GPU completion wait per real frame instead of a wait per generated frame.
Generation still consumes GPU time and can reduce the base rendering FPS.
 A dedicated presenter displays the intermediate
and real frames at processing-interval / multiplier spacing. A three-slot queue bounds
buffering, drops obsolete pending frames, and avoids interpolating across dropped
frames. Frame generation is reset on scene cuts, comparison-wipe changes,
capture changes, resize and bypass. The DLL's disable-interpolation output is
also respected. Initialization/evaluation/presentation failures fall back to the
ordinary path for the rest of the process.

This is an experiment with **estimated screen-space motion and constant depth**,
not an engine integration. Game UI is already baked into the captured image;
occlusions, particles, text and camera changes may produce artifacts. The app's
own menu is drawn separately. Validate visual quality in the intended game.
Frame pacing adds roughly (multiplier - 1) / multiplier of a processing interval
to the real frame's display time, plus inference/copy costs; higher output frequency does not mean lower input
latency. Monitor refresh and the desktop compositor limit actual visible frames.

The menu FPS continues to measure the real processing loop. `[fg] displayed ...`
in `NeuralScreen.log` counts successful presentation calls, including generated
frames; it is not a measurement of monitor scanout. Screenshots, recordings and
Spout remain real SDR frames at the processing rate.

## Checks

```
native\build-host.bat
runtime\python.exe tests\test_frame_generation.py --run
runtime\python.exe tests\test_frame_generation.py --hdr --dynamic --check-pixels
```

The opt-in GPU test briefly opens a 640x360 overlay, checks increased presentation
frequency on a moving source, bypass pixel export, resumption and shutdown.
The pixel check reads generated HDR10 buffers and checks bright-white luminance
and black pixels for 2x, 3x and 4x. `native/test-hdr.bat` verifies the PQ transform
against absolute luminance reference values.
It requires an RTX GPU and the local NR and FG DLLs. HDR transition checks can be
run with `NS_FRAMEGEN=1` and `tests\test_hdr_capture.py --run` or `--desktop`.

DLL used during development: NVIDIA DLSS-G MFGLW 310.9.1.0. No DLL is committed.

## Local Python environment

`runtime` is now a real directory containing a separate Python 3.11.14 runtime
and dependencies, replacing the broken junction to a deleted release folder.
`runtime\python.exe` and `runtime\pythonw.exe` retain the launcher's expected
paths. `requirements-runtime.txt` records the installed package versions.

Reference: [NVIDIA DLSS-G integration guide](https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS_G.md).

## Matched capture and motion

The application sends CAP1 and waits for its acknowledgement before reading
luminance for motion estimation. The subsequent FRM1 carries bit 12 and consumes
the exact captured image with the same frame ID, without capturing again.
Capture changes and resize invalidate a prepared frame. Missing IDs and failed
gray updates are rejected rather than using motion for a different image.
Older standalone clients retain the original single-message capture protocol.

## Optional Super Resolution

Boost and **DLSS Super Resolution** have independent toggles and sliders:

- DLSS input resolution reduces capture before neural rendering (25% to 100%
  of output width and height).
- Boost sets the NR resolution relative to this reduced image. Its residual
  composite also runs at the reduced DLSS input size, not at full output size.
- Motion scales convert guide-grid pixel units to the respective NR/SR units.
- SR also works with Boost off. Enabling SR never enables Boost or changes its
  saved ratio. Changing Boost never changes the SR slider.

The path is capture -> reduce to DLSS input -> NR (with optional Boost composite) -> DLSS SR
-> HDR composition -> optional FG -> output. Output dimensions remain fixed.
The UI saves `work_scale` and `dlss_sr_scale` separately. SSC1 changes only the
SR input scale and acknowledges before CAP1/FRM1. The existing NR feature stays
alive; NR input/output textures and subrects change, and temporal history resets.
SR has separate shader descriptors so its scaling
cannot overwrite descriptors for the Boost passes recorded in the same list.
SR evaluation failure scales the reduced NR result to the output size for that
frame, then returns to the ordinary NR path and clears the SR checkbox.

`native/nvngx_dlss.dll` (310.8.0.0) is separate from NR and FG; no DLL is committed.
`NS_DLSS_SR=1` enables SR in standalone tests; the application uses explicit UI
flags (bit 14: override; bit 13: enabled). The default independent SR scale is 65%.
This is experimental: depth is constant and motion is estimated from capture.
SR adds GPU work while reducing the pixels sent to NR. Net FPS and desktop-text
quality still depend on the settings and scene; there is no output-size slider.

Compounded reductions are guarded in both the client and native worker. The
processing floor is 256x144, preserving source aspect ratio when a requested
size falls below it. Sources smaller than the floor are not enlarged beyond
their own dimensions. The menu displays effective, clamped dimensions; saved
ratios can remain lower. In particular, 10% Boost plus 25% SR input on a 1440p
capture now feeds NR at 256x144 rather than the unstable 64x64 configuration.

Colour reductions use pixel-area averaging, including the reduction before
NR; motion interpolation stays bilinear. Successful SR output receives a
mild five-tap sharpening pass (strength 0.3), constrained to local channel
min/max and preserving alpha. It replaces the final SR copy and runs before
HDR composition and FG. Bypass remains untouched. It improves edge contrast
but cannot reconstruct details lost at very low input resolutions.

Additional checks:

```
runtime\python.exe tests\test_prepared_capture.py --run
runtime\python.exe tests\test_frame_generation.py --hdr --dynamic --sr --check-pixels
runtime\python.exe tests\test_super_resolution.py --run
```
