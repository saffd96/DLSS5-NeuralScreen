# Combined preview updated to v1.8.2

Merged upstream main at 8098ccf into feature/gpu-motion-preview, retaining SR,
DLAA at 100%, FG texture handoff, UI protection, GPU LK and existing library
controls. Published feature PR branches are unchanged by this local merge.

Integration points:
- All custom protocol replies use the upstream private wire handle.
- Prepared capture uses the bounded no-colour retry before CPU guides are
  computed, and preserves acquisition timestamps into the consumed frame.
- SDR tail deferral supports GPU LK fence submission. FG retains its separate
  paced presentation path and completion waits. HDR follows upstream's
  synchronous presentation path.
- HDR capture-format detection, SDR colour-space handling and display-mode
  recovery retain upstream fixes. FG reports display-mode changes through the
  same recovery mechanism, using an atomic stale flag across its threads.
- The original personal config is restored after testing. HDR compatibility
  stays enabled for this existing preview, matching its pre-update behaviour;
  clean configurations use the upstream off-by-default HDR setting.

Validation on RTX 5080:
- Native worker builds; WARP HDR shader checks pass.
- SR reduction, independent Boost, DLAA 100%, bypass, toggle and resize pass.
- Prepared capture pairs remain exact and stale IDs are rejected.
- Final FG HDR/SR/UI run passes 2x/3x/4x, six HDR10 pixel readbacks, bypass,
  stop/resume and shutdown.
- CPU/GPU flow quality harness completes; known large-motion LK limitations
  remain. SDR GPU motion also completes a 220-frame run with tail deferral.
- Frame-retirement tests pass: failed Close, allocator rollover, WGC/DDA,
  phase on/off, gray, pixels, bypass, rebuild and EOF.
- Initial broad suite: 112/117 green. Three functional failures were corrected
  or rerun: frame-retirement source guard, one-line hints in all 12 languages,
  and the interactive window test (initially captured a different window).
  The isolated window rerun checks position, minimize, live resize, return to
  full screen and capture exclusion successfully.
- Two release-packaging checks are not green: no full release ZIP is built,
  and the static check saw the in-progress merge. This is a local source/build
  update, not a validated distribution archive.

Raw validation logs are under `_work/v1.8.2-*.log`. Rollback source is retained
in `archive/preview-before-v1.8.2`; original config and worker were also saved
under the root checkout's `_work/preview-before-v1.8.2-*`.
