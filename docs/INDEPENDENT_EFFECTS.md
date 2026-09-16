# Independent effects

The NR switch controls neural rendering, not the entire processing pipeline.
With NR disabled, capture still feeds the enabled effects in this order:

`capture -> optional SR/DLAA -> optional sharpness -> optional FG -> presentation/export`

With NR enabled the existing reduction / NR / SR flow remains in place.
HDR presentation requires NR **and** the HDR compatibility setting. Turning NR
off switches presentation to SDR without changing the saved HDR preference;
turning NR back on restores HDR where the captured source supports it. The
existing FP16 capture and SDR proxy conversion are retained.

Boost and the model's parameters only affect NR. NR OFF skips both its warmup
and evaluation; SR uses the reduced capture directly instead of a neural
result. Existing worker/device initialization still occurs. Motion guides
continue for SR/DLAA and FG, but spatial sharpening alone needs none. UI
protection still follows FG. With every effect disabled, output is the raw
capture, byte-exact for the SDR pipe-input path.

Verification on RTX 5080:

- `tests/test_independent_effects.py --run`: NR off with sharpening, DLAA,
  reduced-input SR, combinations, Boost independence, raw output and NR resume.
- `tests/test_frame_generation.py --hdr --dynamic --sr --ui --detail --nr-off`:
  421 frames, zero neural evaluations, FG 2x/3x/4x, SDR output despite HDR capture.
- `tests/test_frame_generation.py --hdr --dynamic --check-pixels --sr --ui --detail`:
  normal NR/HDR path, HDR restoration after NR resumes, six generated buffers.
- Existing bypass, SR resize/toggle, sharpness readback, guide ordering and
  module checks also pass.

`FRAME_FLAG_BYPASS` retains its wire value but now means NR disabled. Clients
wanting raw output must disable the independent effects explicitly as well.
