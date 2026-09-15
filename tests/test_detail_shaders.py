"""Run the production spatial detail shader on WARP."""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BAT = BASE / "native" / "test-detail.bat"


def main() -> int:
    if not BAT.exists():
        print(f"FAIL: no {BAT}")
        return 1
    try:
        r = subprocess.run(["cmd", "/c", str(BAT)], cwd=str(BAT.parent),
                           capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL: the WARP shader run did not finish in 300s")
        return 1
    out = (r.stdout or "") + (r.returncode and (r.stderr or "") or "")
    for line in (r.stdout or "").splitlines():
        if line.strip() and not line.startswith("hdr_gpu.cpp"):
            print(f"    {line.strip()}")
    if "is not recognized" in out or "vcvars64" in out and r.returncode != 0:
        print("FAIL: no Visual Studio build tools - the same ones the worker "
              "is built with (native\\build-host.bat)")
        return 1
    if r.returncode != 0 or "PASS" not in (r.stdout or ""):
        print((r.stderr or "").strip()[-600:])
        print(f"FAIL: the detail shader did not pass on WARP (exit {r.returncode})")
        return 1
    print("OK: the spatial detail shaders are right on WARP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
