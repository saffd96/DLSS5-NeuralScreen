"""Historical output-size benchmark for the pre-reorder native worker.

The resolution assertion deliberately rejects the newer pre-NR reduction path:
its Boost ratio changes NR dimensions, invalidating this fixed-NR comparison.

Fixed NR 1280x720 and SR input 1536x864; variable output, no capture/flow/HDR.
The current worker ties its full-size NR composite to the output size, so
this measures the entire synthetic SDR worker, not an isolated SR operation
or the future application's independent output control. User config is untouched.
"""
import json
import os
from pathlib import Path
import re
import statistics
import struct
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
import protocol as wire
from test_prepared_capture import exact


def run_case(width, fg, repeat, directory):
    height = width * 9 // 16
    nrw, nrh = 1280, 720
    srw, srh = 1536, 864
    scale = srw * 100 // width
    assert width * scale == srw * 100
    rng = np.random.default_rng(73)
    low = rng.integers(20, 220, (108, 192, 3), dtype=np.uint8)
    source = cv2.resize(low, (srw, srh), interpolation=cv2.INTER_LINEAR)
    frames = []
    for i in range(8):
        rgb = np.roll(source, i * 4, axis=1)
        rgb = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_LINEAR)
        rgba = np.full((height, width, 4), 255, np.uint8)
        rgba[:, :, :3] = rgb
        frames.append(rgba)
    motion = np.zeros((nrh, nrw, 2), np.float16)
    motion[:, :, 0] = -4 * nrw / srw
    env = dict(os.environ, NS_NR_SMALL="1", NS_DLSS_SR="1", NS_FRAMEGEN="1" if fg else "0",
               NS_HDR="0", NS_PHASE="1", NS_SPOUT="0")
    env.pop("NS_FG_DUMP", None)
    worker = subprocess.Popen([str(ROOT / "native/nvngx.dll"), "--live"],
        cwd=ROOT / "native", env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    logs = []
    def drain():
        for line in iter(worker.stderr.readline, b""):
            logs.append((time.perf_counter(), line.decode("utf-8", "replace")))
    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    watchdog = threading.Timer(60, worker.kill)
    watchdog.start()
    shm = wire.SharedFrameBuffer(width, height, nrw, nrh)
    def ack(fmt):
        return struct.unpack(fmt, exact(worker.stdout, struct.calcsize(fmt)))
    def frame(index, pixels=False):
        wire.send_frame(worker, index, frames[index % 8], motion, index == 0,
            index, shm, want_pixels=pixels, skip_static=False,
            frame_generation=fg, frame_multiplier=2, dlss_sr=True)
        result = ack(wire.OUT_FMT)
        assert result[1] == index and result[2] == 1, result
        if result[3]:
            output = np.frombuffer(exact(worker.stdout, result[3]), np.uint8).reshape(height, width, 4)
            assert output[:, :, :3].mean() > 10 and output[:, :, :3].std() > 5
    try:
        worker.stdin.write(struct.pack(wire.HEADER_FMT, wire.VIDEO_MAGIC, nrw, nrh,
            1, 0, 0, 0, 1, 0, 0, 1., 1., 1., -1., width, height))
        worker.stdin.write(struct.pack(wire.SHM_FMT, wire.SHM_MAGIC,
            shm.color_capacity, shm.motion_capacity, 0, 0, shm.name.encode("ascii")))
        worker.stdin.flush()
        result = ack(wire.SHM_ACK_FMT)
        assert result[1] == 1, result
        shm.negotiated = True
        worker.stdin.write(struct.pack(wire.FRAME_FMT, wire.SR_SCALE_MAGIC, 0, scale, 0, 0))
        worker.stdin.flush()
        assert ack(wire.OUT_FMT)[2] == 1
        wire.send_window(worker, width, height)
        assert ack(wire.WINDOW_ACK_FMT)[1] == 1
        for i in range(100):
            frame(i, pixels=i == 99)
        started = time.perf_counter()
        timings = []
        i = 100
        while time.perf_counter() - started < 6:
            tick = time.perf_counter()
            frame(i)
            timings.append((time.perf_counter() - tick) * 1000)
            i += 1
        ended = time.perf_counter()
        frame(i, pixels=True)
        worker.stdin.close()
        worker.wait(timeout=10)
        assert worker.returncode == 0
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait()
        watchdog.cancel()
        thread.join(timeout=3)
        shm.close()
    full_log = "".join(line for _, line in logs)
    name = f"out-{width}-fg{2 if fg else 0}-r{repeat}"
    (directory / f"{name}.log").write_text(full_log, encoding="utf-8")
    assert f"NR {nrw}x{nrh}; SR input {srw}x{srh} -> {width}x{height}" in full_log
    assert "[sr] first evaluation succeeded" in full_log
    assert "[sr] Evaluate failed" not in full_log and "[sr] CreateFeature failed" not in full_log
    if fg:
        assert "[fg] 2x enabled" in full_log
        assert "[fg] Evaluate failed" not in full_log and "[fg] presenter failed" not in full_log
    measured_log = "".join(line for tick, line in logs if started + 2.1 < tick < ended)
    means = {}
    for phase in ("upload", "eval", "present", "frame", "eval on GPU"):
        values = re.findall(r"\| " + phase + r" ([\d.]+)/", measured_log)
        if values:
            means[phase] = statistics.mean(map(float, values))
    presented = list(map(float, re.findall(r"\[fg\] displayed ([\d.]+) FPS", measured_log)))
    result = dict(width=width, height=height, fg=fg, repeat=repeat,
        frames=len(timings), seconds=ended-started, fps=len(timings)/(ended-started),
        median_ms=float(np.median(timings)), p95_ms=float(np.percentile(timings, 95)),
        phases_ms=means, present_calls_fps=statistics.mean(presented) if presented else None)
    print(json.dumps(result), flush=True)
    return result


def summarize(directory):
    results = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    rows = []
    for width in (2560, 1920, 1536, 3840):
        off = [r for r in results if r["width"] == width and not r["fg"]]
        on = [r for r in results if r["width"] == width and r["fg"]]
        assert len(off) == 3 and len(on) >= 3
        rows.append(dict(width=width, height=width*9//16,
            no_fg_fps=statistics.median(r["fps"] for r in off),
            fg_real_fps=statistics.median(r["fps"] for r in on),
            fg_present_calls=statistics.median(r["present_calls_fps"] for r in on),
            no_fg_range=[min(r["fps"] for r in off), max(r["fps"] for r in off)],
            fg_range=[min(r["fps"] for r in on), max(r["fps"] for r in on)],
            fg_runs=len(on),
            fg_present_range=[min(r["present_calls_fps"] for r in on), max(r["present_calls_fps"] for r in on)],
            fg_p95_ms=statistics.median(r["p95_ms"] for r in on)))
    for row in rows:
        row["no_fg_gain_pct"] = (row["no_fg_fps"] / rows[0]["no_fg_fps"] - 1) * 100
        row["fg_real_gain_pct"] = (row["fg_real_fps"] / rows[0]["fg_real_fps"] - 1) * 100
    (directory / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    text = ["# DLSS output-size sensitivity benchmark", "",
        "2026-09-12. RTX 5080, driver 616.64. Desktop 2560x1440, approximately 165 Hz.", "",
        "Three initial runs per condition, plus control reruns where present pacing varied. "
        "100 warm-up frames then six measured seconds. "
        "Order rotated; medians below. Same synthetic moving scene, NR 1280x720, "
        "SR input 1536x864 in every run. Genuine NVIDIA SR and FG DLLs. "
        "Pixel exports validated before and after each measured interval. "
        "No capture, CPU optical flow, HDR or UI detection. User config unchanged.", "",
        "| Output | Real FPS, FG off | Real FPS, FG x2 (range) | Median gain vs 1440p with FG | FG Present calls/s |",
        "|---|---:|---:|---:|---:|"]
    for row in rows:
        text.append(f"| {row['width']}x{row['height']} | {row['no_fg_fps']:.1f} | "
                    f"{row['fg_real_fps']:.1f} ({row['fg_range'][0]:.1f}-{row['fg_range'][1]:.1f}) | {row['fg_real_gain_pct']:+.1f}% | "
                    f"{row['fg_present_calls']:.1f} |")
    text += ["", "## Interpretation and limits", "",
        "Lower output is not automatically higher displayed FPS. The 1440p FG "
        "runs had substantial variation, including a run faster than every 1080p "
        "run. A stable FG throughput gain from lower output is therefore not "
        "established. Present calls are not measured scanouts or "
        "input-to-photon latency. The shared GPU queue, frame dropping and display "
        "pacing contribute to non-monotonic results. NR GPU time stays near 2.8 ms.", "",
        "This is an approximate pipeline sensitivity test, not an isolated timing "
        "of the proposed output slider. The current worker couples its full-size "
        "source/composite/swapchain to output size; CPU shared-memory copies and "
        "GPU uploads therefore vary too. Capture and final stretching to a fixed "
        "monitor size are absent. The future independent-output pipeline could "
        "have different throughput. No conclusion about HDR speed or visual quality.", "",
        "See results.json for every run and the .log files for native phase timings."]
    (directory / "REPORT.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))


def main():
    if "--run" not in sys.argv:
        print("SKIP: --run runs a synthetic GPU benchmark; may show the output window")
        return
    import autocheck
    assert not autocheck.running_instances(), "NeuralScreen is running; benchmark would contend for GPU"
    cv2.setNumThreads(4)
    directory = ROOT / "_work" / "dlss-output-benchmark"
    directory.mkdir(exist_ok=True)
    results = []
    # Rotate order to avoid assigning warm caches/temperature to one resolution.
    widths = [2560, 1920, 1536, 3840]
    for repeat in range(3):
        order = widths[repeat:] + widths[:repeat]
        for fg in ((False, True) if repeat % 2 == 0 else (True, False)):
            for width in order:
                results.append(run_case(width, fg, repeat, directory))
                (directory / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    summarize(directory)


if __name__ == "__main__":
    main()
