"""Run both local demo servers; Ctrl+C stops both process trees."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not python.exists() or npm is None or not (ROOT / "apps/web/node_modules").is_dir():
        print("Install dependencies first; see README.md.", file=sys.stderr)
        return 1
    for port in (8000, 3000):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                print(f"Port {port} is in use. Stop that server before starting the demo.", file=sys.stderr)
                return 1
    children: list[subprocess.Popen] = []
    print("Campaign Launchpad: http://localhost:3000 | API: http://127.0.0.1:8000/docs", flush=True)
    print("Local single-workspace demo. Press Ctrl+C to stop both servers.", flush=True)
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    try:
        children.append(subprocess.Popen(
            [str(python), "-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT, **options,
        ))
        children.append(subprocess.Popen(
            [npm, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000"],
            cwd=ROOT / "apps/web", **options,
        ))
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        print("A server exited; stopping the other server.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is not None:
                continue
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
