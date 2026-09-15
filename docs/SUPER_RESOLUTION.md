# Experimental DLSS Super Resolution

This change adds an independently controlled DLSS input scale. Capture is
reduced before neural rendering; DLSS SR restores the native output size.
Boost continues to control neural resolution relative to that reduced input.
Area filtering limits aliasing during reduction, and bounded sharpening follows SR.

SR is off by default. Enable it in the processing menu. `native/nvngx_dlss.dll`
is required and is not stored in git. Missing/failed SR falls back to neural
rendering without SR. Processing dimensions are clamped to a safe minimum.

Capture and grayscale guides are latched together before motion estimation.
This is desktop reconstruction with estimated motion and flat depth, not an
engine integration with ground-truth depth, motion vectors and jitter.

Validation:
- `runtime/python.exe tests/test_super_resolution.py --run`
- `runtime/python.exe tests/test_prepared_capture.py --run`
- `runtime/python.exe tests/test_quality_gpu.py --run`
- `runtime/python.exe tests/test_resolution_limits.py`
- `runtime/python.exe tests/test_motion_floor.py`

The native tests require Windows and an NVIDIA GPU; shader tests use WARP and MSVC.

## Native-size passthrough

At 100% input resolution SR/DLAA is bypassed. The ordinary NR result is used
without an extra temporal reconstruction pass. The same applies when the minimum
size guard rounds the requested input back to output size. This is not DLAA;
the UI labels the endpoint 1:1. It avoids the softness observed with captured
frames that lack native engine depth and jitter. Below native size SR remains
experimental. The GPU regression checks that native SR on/off output is byte-exact.
