"""Synthetic HUD over a moving scene, disappearance, cuts and wire bounds."""
import io
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from ui_detection import UIRegionDetector
from guides import TemporalGuideGenerator
from protocol import send_ui_regions


def main():
    rng = np.random.default_rng(42)
    background = rng.integers(25, 150, (180, 320), dtype=np.uint8)
    hud = np.full((24, 76), 25, np.uint8)
    cv2.putText(hud, "HP 100", (3, 18), cv2.FONT_HERSHEY_SIMPLEX, .55, 245, 1)

    def frame(i, show=True):
        result = np.roll(background, i * 2, axis=1).copy()
        if show:
            result[145:169, 12:88] = hud
        return result

    def mask(regions):
        result = np.zeros((180, 320), np.uint8)
        for x, y, r, b in regions:
            result[y * 180 // 65535:b * 180 // 65535,
                   x * 320 // 65535:r * 320 // 65535] = 1
        return result

    detector = UIRegionDetector()
    started = time.perf_counter()
    for i in range(40):
        regions = detector.process(frame(i))
    elapsed = (time.perf_counter() - started) / 40 * 1000
    detected = mask(regions)
    assert detected[145:169, 12:88].sum() > 200, regions
    outside = detected.copy()
    outside[145:169, 12:88] = 0
    assert outside.sum() == 0, "moving world falsely protected"
    assert not detector.process(frame(40, False)), "disappeared HUD remained protected"
    assert not detector.process(frame(41), reset=True), "scene cut retained regions"
    detector.reset()
    for _ in range(30):
        assert not detector.process(frame(0)), "static desktop learned as HUD"
    for i in range(30):
        assert not detector.process(frame(i, False)), "panning texture learned as HUD"

    guides = TemporalGuideGenerator(320, 180, emit_small=True)
    for i in range(20):
        guide = guides.process(gray=frame(i), detect_ui=True)
    assert guide.ui_regions
    assert not guides.process(gray=frame(20), detect_ui=False).ui_regions
    assert not guides.process(gray=frame(21), detect_ui=True).ui_regions
    assert not guides.zero_guide().ui_regions

    worker = SimpleNamespace(stdin=io.BytesIO())
    send_ui_regions(worker, 1, ())
    assert not worker.stdin.getvalue(), "disabled detection should have no payload"
    send_ui_regions(worker, 2, ((100, 200, 300, 400),))
    send_ui_regions(worker, 3, ())
    send_ui_regions(worker, 4, ())
    payload = worker.stdin.getvalue()
    assert len(payload) == 56
    assert struct.unpack("<4Iq", payload[:24]) == (0x31524955, 2, 1, 0, 0)
    assert struct.unpack("<4H", payload[24:32]) == (100, 200, 300, 400)
    assert struct.unpack("<4Iq", payload[32:]) == (0x31524955, 3, 0, 0, 0)
    for invalid in (((0, 0, 0, 1),), ((-1, 0, 1, 1),), ((0, 0, 65536, 1),), ((0, 0, 1, 1),) * 33):
        try:
            send_ui_regions(worker, 5, invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid rectangles accepted")
    print(f"PASS: HUD detection/reset/disable/protocol; {elapsed:.2f} ms/frame at 320x180")


if __name__ == "__main__":
    main()
