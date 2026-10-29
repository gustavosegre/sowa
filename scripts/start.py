"""Run Forja for everyday local use: one process (API + built web app) on 127.0.0.1. Ctrl+C stops it.

Builds the web app first when apps/web/dist is missing or older than the sources, then opens the
browser at the address with the access token (#token=, as Flowa prints it).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "apps" / "web"
DIST = WEB / "dist" / "index.html"


def _newest(paths: list[Path]) -> float:
    return max((f.stat().st_mtime for p in paths for f in (p.rglob("*") if p.is_dir() else [p]) if f.is_file()), default=0)


def _needs_build() -> bool:
    if not DIST.exists():
        return True
    sources = [WEB / "src", WEB / "index.html", WEB / "public", WEB / "package.json", WEB / "vite.config.ts"]
    return _newest([p for p in sources if p.exists()]) > DIST.stat().st_mtime


def _build() -> None:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("Para compilar a interface é preciso o pnpm (rode `make setup`).")
    print("Compilando a interface (só na primeira vez ou depois de mudanças)...", flush=True)
    subprocess.run([pnpm, "exec", "vite", "build"], cwd=WEB, check=True)


def _wait_ready(url: str, api: subprocess.Popen[bytes], timeout: float = 90) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and api.poll() is None:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(0.3)
    return False


def _token(env: dict[str, str]) -> str | None:
    if env.get("FORJA_AUTH_ENABLED", "").lower() in ("0", "false", "no"):
        return None
    if env.get("FORJA_TOKEN", "").strip():
        return env["FORJA_TOKEN"].strip()
    path = Path(env["FORJA_DATA_DIR"]) / "token"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="8765")
    ap.add_argument("--build", action="store_true", help="recompila a interface mesmo sem mudanças")
    ap.add_argument("--no-browser", action="store_true", help="não abre o navegador")
    args = ap.parse_args()

    if args.build or _needs_build():
        _build()

    url = f"http://127.0.0.1:{args.port}"
    env = {**os.environ, "FORJA_WEB_URL": url, "FORJA_SERVE_WEB": "true"}
    env.setdefault("FORJA_DATA_DIR", str(ROOT / "data"))
    uv = shutil.which("uv") or "uv"
    api = subprocess.Popen(
        [uv, "run", "uvicorn", "forja.main:app", "--host", "127.0.0.1", "--port", args.port],
        cwd=ROOT / "apps" / "api",
        env=env,
    )
    try:
        if not _wait_ready(url, api):
            print("A Forja não subiu; veja as mensagens acima.", flush=True)
            return api.wait() or 1
        token = _token(env)
        address = f"{url}/#token={token}" if token else url
        print(f"\n  Forja no ar. Abra:\n\n    {address}\n\n  Dados em {env['FORJA_DATA_DIR']}. Ctrl+C para parar.\n", flush=True)
        if not args.no_browser:
            webbrowser.open(address)
        return api.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        if api.poll() is None:
            api.terminate()
            try:
                api.wait(timeout=10)
            except subprocess.TimeoutExpired:
                api.kill()


if __name__ == "__main__":
    raise SystemExit(main())
