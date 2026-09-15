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

## Experimental integration (2026-09-14)

Merged upstream experimental at fc6af02 while retaining local SR, UI protection,
GPU LK and opt-in library updates. Main is still v1.9.0 at b18980f at this time.
Latest FG pacing, window flicker fixes, displayed FPS and multiplier controls
are retained. Guides run once after prepared capture; the duplicate processing
in the upstream experimental loop was removed. Hardware backend failure resets
history and resumes CPU DIS. Updates remain off by default; the opt-in persists.
SR and FG load from native/libraries first, then native; updates follow that path.
SR/DLAA remain available locally but disabled in the personal configuration.

Integration validation: native build, module/config/i18n checks, GPU/NVOFA/FG
controls, UI detection and offline updater tests. Real GPU tests exercised SR
reduction, 100% DLAA, bypass and resize; HDR FG with dynamic multiplier and UI
protection completed cleanly. Full suite has not been run for this merge.

The subsequently published v1.10.0 main (e69bc0d) is now merged too. The separate
NVOFA follow-up includes the single-update regression and cost-calibration harness.
See NVOFA_COST_VALIDATION.md: 71 captured pairs did not justify a global cost mask,
so normal rendering still uses unfiltered NVOFA. The combined app smoke delivered
2361 frames with NVOFA and HDR FG active and no guide-processing errors.

## v1.11.0 integration (2026-09-15)

Merged upstream main at 7a27455, including WGC queue draining, z-order fixes,
FG refusal feedback and hotkey, GPU identity and NGX diagnostics. Retained SR,
GPU LK, UI protection and opt-in library updates. Combined SR motion scaling and
protocol commands coexist with parameter read-back and capture-stall resets.

Validation: native build; 14 targeted Python/config/UI checks; GPU SR/DLAA toggle,
resize and bypass; HDR FG dynamic multiplier with UI protection; prepared capture.
Personal configuration is restored separately and is not committed.
