# SR and FG overhead follow-up

SR's native-resolution bypass was reverted at the user's request. At 100%,
DLSS runs DLAA, with that mode and its extra GPU work explicitly labeled in
the UI. The SR label change is maintained in the dedicated SR branch/PR #53.
FG optimization is maintained in its branch/PR #54. This combined preview
includes both; the standalone GPU-motion PR #55 includes neither.

FG still runs after neural rendering. Generated textures are transferred to
a reserved presentation slot by exchanging resource ownership instead of
copying their pixels. All interchangeable textures support UAV writes and
rest in COPY_SOURCE state. A slot is published only after the producer fence
completes; the presenter holds its slot until presentation copies complete.
The real neural frame still needs a copy. Pacing and interpolation rejection
remain in place. This does not eliminate the cost of DLSS-G inference.

## Validation on RTX 5080

- Native worker build passed.
- The earlier SR bypass regression passed before the bypass was reverted.
  The SR branch's existing DLAA-at-100%, toggle, bypass and resize test passes.
- `tests/test_frame_generation.py --run --hdr --dynamic --check-pixels --sr --ui`:
  multipliers 2x/3x/4x, stop/resume and shutdown pass. Six generated HDR10
  buffers preserve bright whites, contain no detected black-frame failure,
  and preserve protected UI pixels exactly.

Short synthetic WGC scrolling benchmark, 2560x1440, GPU motion, FG 2x, SR off:
220 iterations per run, discard first 40, old/new/new/old order. Mean of the
two run medians for complete frame processing: old 10.952 ms, new 10.645 ms
(about 2.8% less time). Worker-only run medians average 9.779 vs 9.544 ms.
Results are noisy: capture changed-frame fractions vary from 0.667 to 0.750,
and the last baseline has latency spikes. This is an indication, not a
guaranteed FPS improvement or a measurement of unique displayed frames.
Local raw results: `_work/fg-copy-abba.json` and
`_work/gpu-flow-results/gpu-fg1-q0-r100` through `r103`.
