# Native-size clarity experiment (2026-09-15)

## Implemented

- SR at 100%, or at native size after minimum-size clamping, uses the ordinary
  NR path. It does not run temporal DLAA. GPU tests verify byte-exact equality
  with SR disabled. Below native size the experimental SR path is retained.
- A separate **Sharpness / Резкость** slider controls a spatial pass on real NR
  output, before HDR reconstruction, frame generation and pixel export.
- Default 0% performs no additional allocation, texture copy or dispatch. NR OFF
  stays a raw bypass. The setting is saved and applied live without restarting.
- Positive strength uses a five-tap unsharp filter with contrast-dependent gain,
  a bounded per-channel change and a local-neighbourhood clamp. Flat areas and
  alpha are preserved. This enhances existing edges; it does not recover missing
  information. It can still emphasize texture/noise, so compare moderate values
  with zero on the actual content.

## Measurements on RTX 5080, driver 616.64

The production HLSL plus one texture copy was timed with GPU timestamp queries
on the hardware D3D11 device at 2560x1440, strength 50%. After five warmups, 25
samples measured median **0.0444 ms**, min 0.0432, max 0.0826. This isolates the
copy/shader; the application executes it in D3D12 and also pays capture, NR, HDR
and presentation costs. It is not an application FPS measurement.

The D3D12 worker A/B test includes upload, NR, sharpening and full pixel readback.
Four interleaved batches (off/on/on/off, 45 measured frames each) averaged:

| Strength | Mean frame time across the two batches |
| --- | ---: |
| 0% | 27.457 ms |
| 50% | 27.602 ms |

The 0.145 ms difference is smaller than the between-run variation; it does not
support a precise application FPS-loss claim. Pixel identity/effect assertions
pass independently of these timings.

## Restoration model: not enabled in the app

Tested `realesrgan-x4plus` in the author's official NCNN Vulkan Windows portable
build dated 20220424. Input 640x360, output 2560x1440, tile 512, GPU 0 (log names
RTX 5080), one processing thread. The five images are four 2-pixel translations
of the upstream `inputs/0014.jpg` cartoon example and a synthetic blurred text
image. Output is also downsampled to input size for a native-size comparison.
The historic artifact filenames say `natural`; the example is a cartoon, not a
photographic benchmark.

Two batch runs took 5.786 and 4.151 seconds including process startup and PNG
I/O. In the second run, completed-image timestamps after the first result were
about **305.5 ms apart** on average (roughly 3.3 images/sec). This is batch
throughput including image I/O, not isolated GPU inference time or game FPS.

Visual inspection found strong shape/edge distortions on the supplied example.
After compensating the known translations, native-size mean absolute differences
were 0.210 / 0.226 / 0.307 on a 0..255 scale away from borders. Small differences
on translations do not establish quality under occlusion or arbitrary motion.

This model/runtime combination is rejected for live integration. This does not
establish that all restoration models are too slow, nor does it distinguish
model behavior from possible issues in this older Vulkan executor. A newer
optimized model/runtime needs its own quality and latency measurements. Nothing
from this experiment is loaded by ordinary application launches.

Source: [Real-ESRGAN official release](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0).
Downloaded Windows ZIP SHA256:
`abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d`.

## Reproduce

```
runtime\python.exe tests\test_detail_controls.py
runtime\python.exe tests\test_detail_shaders.py
_work\detail_gpu.exe --bench
runtime\python.exe tests\experiment_detail.py --run
runtime\python.exe tests\test_super_resolution.py --run
runtime\python.exe tests\test_frame_generation.py --run --hdr --dynamic --ui --check-pixels --detail
runtime\python.exe tests\experiment_restoration_model.py --tools ..\restoration-tools
```

The last command requires the explicitly downloaded official portable runtime
under `ncnn/` and the example image saved as `natural.jpg`. It does not download
or install anything itself. Results stay in `_work/detail-results/` and unique
`_work/restoration-results/<run-id>/` directories. Model/runtime files are not
bundled or committed.

Validation passed: shader zero/flat identity, alpha and bounds; config, slider,
wire caching and persistence; native SR equivalence; SR resize/bypass; six
generated HDR10 buffers with sharpness and UI protection, preserving bright
whites without black frames. Full suite not rerun.
