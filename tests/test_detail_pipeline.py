"""Opt-in NVIDIA readback: live sharpness changes after NR, SR and DLAA."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
import protocol as wire
from test_prepared_capture import exact


def capture(name, sr, scale, baseline=False, source_image=None, strengths=(0, 50, 100, 0)):
    w, h = 640, 360
    source = np.full((h, w, 4), (90, 90, 90, 255), np.uint8)
    cv2.putText(source, 'Soft text 0123', (25, 110), cv2.FONT_HERSHEY_SIMPLEX,
                1.8, (160, 160, 160, 255), 3, cv2.LINE_AA)
    cv2.rectangle(source, (80, 180), (540, 300), (190, 150, 120, 255), -1)
    source = cv2.GaussianBlur(source, (9, 9), 1.6)
    if source_image is not None:
        source = np.ascontiguousarray(source_image)
        h, w = source.shape[:2]
    motion = np.zeros((h, w, 2), np.float16)
    env = dict(os.environ, NS_HDR='0', NS_FRAMEGEN='0', NS_NR_SMALL='0')
    worker = subprocess.Popen([str(ROOT/'native/nvngx.dll'), '--live'],
        cwd=ROOT/'native', env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    logs = []
    thread = threading.Thread(target=lambda: logs.extend(iter(worker.stderr.readline, b'')), daemon=True)
    thread.start()
    watchdog = threading.Timer(90, worker.kill)
    watchdog.start()
    folder = ROOT/'_work/sharpness-check'
    folder.mkdir(parents=True, exist_ok=True)

    def ack():
        a = struct.unpack(wire.OUT_FMT, exact(worker.stdout, struct.calcsize(wire.OUT_FMT)))
        assert a[2] == 1, a
        return a

    def control(magic, value):
        worker.stdin.write(struct.pack(wire.FRAME_FMT, magic, 0, value, 0, 0))
        worker.stdin.flush()
        assert ack()[3] == 0

    try:
        worker.stdin.write(struct.pack(wire.HEADER_FMT, wire.VIDEO_MAGIC,
            w, h, 1, 0, 0, 0, 1, 0, 0, 0., 0., 0., -1., w, h))
        worker.stdin.flush()
        index = 0
        control(wire.SR_SCALE_MAGIC, scale)
        results = []
        for strength in strengths:
            control(wire.DETAIL_MAGIC, 0 if baseline else strength)
            # Reset identical source to isolate spatial changes from history.
            for _ in range(3):
                wire.send_frame(worker, index, source, motion, True, index, dlss_sr=sr)
                index += 1
                a = ack()
                assert a[3] == w*h*4
                out = np.frombuffer(exact(worker.stdout, a[3]), np.uint8).reshape(h, w, 4).copy()
            results.append(out)
            cv2.imwrite(str(folder/f'{name}-{len(results)}-{strength}-baseline{int(baseline)}.png'), cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA))
        # Keep saved strength while SR is toggled off and back on live.
        control(wire.DETAIL_MAGIC, 0 if baseline else 100)
        for enabled in (False, sr):
            for _ in range(3):
                wire.send_frame(worker, index, source, motion, True, index, dlss_sr=enabled)
                index += 1
                a = ack()
                assert a[3] == w*h*4
                out = np.frombuffer(exact(worker.stdout, a[3]), np.uint8).reshape(h, w, 4).copy()
            results.append(out)
        control(wire.DETAIL_MAGIC, 0)
        wire.send_frame(worker, index, source, motion, True, index, bypass=True, dlss_sr=False)
        index += 1
        a = ack()
        assert np.array_equal(np.frombuffer(exact(worker.stdout, a[3]), np.uint8).reshape(h, w, 4), source)

        worker.stdin.close()
        worker.wait(timeout=10)
        assert worker.returncode == 0
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait()
        watchdog.cancel()
        thread.join(timeout=2)
        (folder/f'{name}-baseline{int(baseline)}-worker.log').write_bytes(b''.join(logs))
    return results


if __name__ == '__main__':
    if '--run' in sys.argv:
        for mode in [('nr', False, 100), ('dlaa', True, 100), ('sr', True, 50)]:
            baseline = capture(*mode, baseline=True)
            enhanced = capture(*mode)
            # SR itself changes over the initial frames even with Reset set.
            # Compare matching frame positions in an unsharpened control run,
            # not unrelated frames at different points in its initialization.
            deltas = []
            for strength, raw, out in zip((0, 50, 100, 0, 100, 100), baseline, enhanced):
                delta = np.abs(out.astype(int)-raw.astype(int))
                assert np.array_equal(raw[:, :, 3], out[:, :, 3]), 'alpha changed'
                if strength == 0:
                    assert np.array_equal(raw, out), f'{mode[0]}: zero changed pixels'
                else:
                    assert delta.max() <= 31, 'unbounded sharpening'
                    assert np.count_nonzero(delta) > 1000, 'too few affected pixels'
                    deltas.append(delta.max())
            assert deltas[0] >= 2 and deltas[1] > deltas[0], 'weak slider response'
            print(f'PASS {mode[0]}: max changes 50%={deltas[0]}, 100%={deltas[1]}; SR toggling preserves sharpening; zero and bypass exact', flush=True)
    else:
        print('SKIP: requires --run and NVIDIA runtime')
