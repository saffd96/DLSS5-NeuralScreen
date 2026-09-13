# NVOFA in the combined preview

The local `feature/gpu-motion-preview` branch includes NVOFA alongside HDR,
Super Resolution/DLAA, Frame Generation, UI protection, GPU LK and the existing
library update controls. Upstream PR #69 remains NVOFA-only against main.

Settings → Capture → Motion estimation selects CPU DIS, GPU LK or NVOFA.
Only one motion estimator runs at a time. The original GPU motion checkbox
remains an alias for selecting GPU LK; enabling NVOFA clears that checkbox.
Old configurations with `gpu_motion: true` migrate to GPU LK automatically.

The prepared-capture sequence remains ahead of Python guides, UI detection
and rendering. NVOFA failure resumes CPU DIS rather than invoking GPU LK.
Other feature settings are preserved when changing the motion estimator.

Validation: native build; NVOFA and GPU controls, FG controls, UI detection;
NVOFA execution-failure fallback; HDR FG ×2/×3/×4 with SR and protected UI
readback (six generated buffers, no black frames); and 220 frames with NVOFA,
SR at 75%, FG ×2 and UI regions enabled together using prepared capture.

Combined smoke command:
`runtime\python.exe tests\experiment_nvofa.py --combined`

Standalone NVOFA benchmark numbers in NVOFA.md do not measure the cost of
enabling every feature at the same time.
