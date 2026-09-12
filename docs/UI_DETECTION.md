# Experimental HUD protection

Enable **HUD protection in FG (experimental)** alongside Frame Generation.
The option is off by default, is saved independently of Boost/SR, and can
be toggled without restarting neural rendering.

The existing small grayscale guide is examined for textured regions that
stay fixed in screen coordinates while the background changes. Eight frames
of motion evidence are required; a static desktop alone is not sufficient.
Scene cuts and changed pixels clear confidence. Turning the option off clears
the detector. At most 32 rectangles covering 20% of the guide are selected.

After DLSS-G evaluates each intermediate frame, the worker copies these
rectangles from the completed real frame into the generated output on the
GPU. This happens after NR, SR and HDR composition. Pixel copies preserve
the SDR/HDR encoding exactly. No additional full-frame readback, neural
model or CPU/GPU frame upload is introduced. UI updates at the real frame
rate; the scene can interpolate between frames. NR and SR still process UI.

This is a screen-space heuristic, not semantic recognition or a real game
HUD layer. Animated/transparent HUD, fine text lost in downsampling and
interfaces without a moving background can be missed. Stationary objects
can be mistaken for UI; rectangular protection can produce visible boundaries.
It does not remove ghosts already produced by NR/SR or reconstruct scenery
hidden behind the HUD. It deliberately does not claim to supply DLSS-G's
Hudless/UIAlpha inputs, which require a properly separated scene and UI.

Protocol: `UIR1` uses the 24-byte frame header (magic `0x31524955`, frame ID,
rectangle count, zero reserved, zero timestamp), followed by up to 32
little-endian `uint16[4]` rectangles (left, top, exclusive right, bottom,
normalized to 0..65535). It has no reply. A packet applies to its matching
next frame only. Control changes invalidate pending regions; UIR1 itself
does not invalidate an already prepared CAP1 capture.

Validation:

```powershell
.\runtime\python.exe tests\test_ui_detection.py
.\runtime\python.exe tests\test_framegen_controls.py
.\runtime\python.exe tests\test_frame_generation.py --hdr --dynamic --sr --check-pixels --ui
```

The GPU test checks exact protected HDR10 pixels at FG x2/x3/x4, including
a deliberately moving boundary; it is not a Dota 2 visual-quality benchmark.
