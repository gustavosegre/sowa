"""Run the API (uvicorn --reload) and the web dev server together. Ctrl+C stops both.

Cross-platform replacement for `a & b` so `make dev` also works on Windows.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-port", default="8000")
    ap.add_argument("--web-port", default="5173")
    args = ap.parse_args()

    uv = shutil.which("uv") or "uv"
    pnpm = shutil.which("pnpm") or "pnpm"
    env = {**os.environ, "FORJA_API_URL": f"http://127.0.0.1:{args.api_port}"}
    env.setdefault("FORJA_DATA_DIR", str(ROOT / ".dev-data"))
    procs = [
        subprocess.Popen(
            [uv, "run", "uvicorn", "forja.main:app", "--reload", "--port", args.api_port],
            cwd=ROOT / "apps" / "api",
            env=env,
        ),
        subprocess.Popen(
            [pnpm, "exec", "vite", "--host", "127.0.0.1", "--port", args.web_port],
            cwd=ROOT / "apps" / "web",
            env=env,
        ),
    ]
    print(f"Forja: web http://127.0.0.1:{args.web_port}  ·  api http://127.0.0.1:{args.api_port}/docs")
    try:
        while all(p.poll() is None for p in procs):
            try:
                procs[0].wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                # Ctrl+C already reaches children sharing the console; this covers the rest.
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
    return max((p.returncode or 0) for p in procs)


if __name__ == "__main__":
    raise SystemExit(main())
