"""Track the backend actually initialized by the current worker."""


def normalize_backend(value):
    """Preserve explicit CPU/GPU LK choices; default to NVOFA."""
    return value if value in ("cpu", "gpu") else "nvofa"


class MotionBackendStatus:
    def __init__(self):
        self.worker = None
        self.active = False
        self.failed = False
        self._scanned = 0

    def update(self, worker, logs):
        if worker is not self.worker:
            self.worker = worker
            self.active = self.failed = False
        # Keep the last verdict when the bounded log buffer rotates.
        for line in reversed(logs):
            if "[nvofa] unavailable:" in line or "[gpu-flow] unavailable:" in line:
                self.active, self.failed = False, True
                break
            if "[nvofa] active:" in line or "[gpu-flow] experimental GPU Lucas-Kanade active" in line:
                self.active, self.failed = True, False
                break
        return self.active
