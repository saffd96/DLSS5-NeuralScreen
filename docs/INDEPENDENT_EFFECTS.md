# Independent effects

The NR switch controls neural rendering, not the entire processing pipeline.
With NR disabled, capture still feeds the enabled effects in this order:

`capture -> optional SR/DLAA -> optional sharpness -> optional FG -> presentation/export`

With NR enabled the existing reduction / NR / SR flow remains in place.
HDR presentation follows the HDR compatibility setting and the captured source,
independently of NR. With NR and effects off, the original FP16 HDR capture
passes through without a neural edit. Independent effects are applied through
the existing SDR proxy/residual reconstruction; FG retains HDR10 output.
Turning NR off does not force SDR. SDR recording/Spout behavior is unchanged.

Boost and the model's parameters only affect NR. NR OFF skips both its warmup
and evaluation; SR uses the reduced capture directly instead of a neural
result. Existing worker/device initialization still occurs. Motion guides
continue for SR/DLAA and FG, but spatial sharpening alone needs none. UI
protection still follows FG. With every effect disabled, output is the raw
capture, byte-exact for the SDR pipe-input path.

Verification on RTX 5080:

- `tests/test_independent_effects.py --run`: NR off with sharpening, DLAA,
  reduced-input SR, combinations, Boost independence, raw output and NR resume.
- `tests/test_frame_generation.py --hdr --dynamic --check-pixels --sr --ui --detail --nr-off`:
  421 frames, zero neural evaluations, FG 2x/3x/4x, HDR10 generated frames and FP16 passthrough.
- `tests/test_frame_generation.py --hdr --dynamic --check-pixels --sr --ui --detail`:
  normal NR/HDR path, HDR retained across NR toggles, six generated buffers.
- Existing bypass, SR resize/toggle, sharpness readback, guide ordering and
  module checks also pass.

`FRAME_FLAG_BYPASS` retains its wire value but now means NR disabled. Clients
wanting raw output must disable the independent effects explicitly as well.
