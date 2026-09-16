"""NVIDIA readback: NR OFF preserves independent effects and raw passthrough."""
import os
from pathlib import Path
import struct
from worker_reply import read_reply
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
import protocol as wire
from test_prepared_capture import exact


def run():
    w, h = 640, 360
    src = np.full((h, w, 4), (45, 75, 110, 255), np.uint8)
    cv2.putText(src, 'Independent effects', (15, 160), cv2.FONT_HERSHEY_SIMPLEX,
                1.3, (220, 190, 170, 255), 3, cv2.LINE_AA)
    src = cv2.GaussianBlur(src, (7, 7), 1.3)
    mv = np.zeros((h//2, w//2, 2), np.float16)
    p = subprocess.Popen([str(ROOT/'native/nvngx.dll'), '--live'], cwd=ROOT/'native',
        env=dict(os.environ, NS_HDR='0', NS_FRAMEGEN='0', NS_NR_SMALL='1'),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW)
    logs = []
    drain = threading.Thread(target=lambda: logs.extend(iter(p.stderr.readline, b'')), daemon=True)
    drain.start()
    timer = threading.Timer(60, p.kill)
    timer.start()

    def ack():
        out = struct.unpack(wire.OUT_FMT, read_reply(p.stdout, struct.calcsize(wire.OUT_FMT)))
        assert out[2] == 1, out
        return out

    def control(magic, value):
        p.stdin.write(struct.pack(wire.FRAME_FMT, magic, 0, value, 0, 0));p.stdin.flush()
        assert ack()[3] == 0

    try:
        p.stdin.write(struct.pack(wire.HEADER_FMT, wire.VIDEO_MAGIC,
            w//2, h//2, 1, 0, 0, 0, 1, 1, 0, 1., 1., 1., -1., w, h));p.stdin.flush()
        # Exercise both DLAA and reduced-input SR without neural rendering.
        results = []
        states = [(False, False, 0, 100), (False, False, 100, 100),
                  (False, True, 0, 100), (False, True, 100, 100),
                  (False, True, 0, 50), (False, True, 100, 50),
                  (False, False, 0, 100), (True, False, 0, 100),
                  (False, False, 0, 100)]
        for i, (nr, sr, strength, scale) in enumerate(states):
            control(wire.DETAIL_MAGIC, strength)
            control(wire.SR_SCALE_MAGIC, scale)
            wire.send_frame(p, i, src, mv, True, i, bypass=not nr, dlss_sr=sr,
                            frame_generation=False)
            a = ack();assert a[3] == src.nbytes
            out = np.frombuffer(exact(p.stdout, a[3]), np.uint8).reshape(src.shape).copy()
            results.append(out)
            if not nr and not sr and strength == 0:
                assert np.array_equal(src, out), 'all effects off changed pixels'
            assert out[:, :, :3].mean() > 20, 'black output'
        assert np.any(results[1] != results[0]), 'sharpness requires NR'
        assert np.any(results[3] != results[2]), 'sharpness after DLAA has no effect'
        assert np.any(results[5] != results[4]), 'sharpness after SR has no effect'
        p.stdin.close();p.wait(timeout=10);assert p.returncode == 0
    finally:
        if p.poll() is None:p.kill();p.wait()
        timer.cancel();drain.join(timeout=2)
    log = b''.join(logs).decode('utf-8', 'replace')
    assert '[sr] first evaluation succeeded' in log
    assert log.count('discarded warmup frames') == 1
    assert '2 direct evaluations' in log, log  # one warmup + the sole NR frame
    print('PASS: NR-independent sharpness, DLAA, SR, combined effects, raw identity and NR resume')


if __name__ == '__main__':
    if '--run' in sys.argv:run()
    else:print('SKIP: use --run for NVIDIA readback')
