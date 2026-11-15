"""Open toolgate Live Lab as native desktop windows (Agent + Tools + Control)."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def ensure_server(host: str, port: int) -> subprocess.Popen | None:
    if _port_open(host, port):
        return None
    env = os.environ.copy()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "toolgate.api.app:create_app",
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(Path(__file__).resolve().parents[3]),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if _port_open(host, port):
            return proc
        time.sleep(0.25)
    raise RuntimeError(f"server did not start on http://{host}:{port}")


def try_open_ollama_app() -> None:
    """Best-effort: show the Ollama desktop app if installed on Windows."""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama app.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
    ]
    for path in candidates:
        if path.is_file():
            try:
                subprocess.Popen([str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
    # Fallback: ensure daemon is up
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def open_with_webview(base: str) -> None:
    import webview

    # Control only — Agent/Tools open automatically during Live Lab runs.
    webview.create_window(
        "toolgate · Control (workflow)",
        f"{base}/",
        width=1280,
        height=860,
        x=40,
        y=40,
    )
    webview.start()


def open_with_browser(base: str) -> None:
    webbrowser.open(f"{base}/")


def launch(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    open_ollama: bool = True,
    force_browser: bool = False,
) -> None:
    if open_ollama:
        threading.Thread(target=try_open_ollama_app, daemon=True).start()

    server = ensure_server(host, port)
    base = f"http://{host}:{port}"
    print(f"toolgate desktop lab → {base}")
    print("Control window open. Agent/Tools launch automatically on Live Lab runs.")

    try:
        if force_browser:
            open_with_browser(base)
            if server:
                server.wait()
            else:
                print("Server already running. Browser tabs opened.")
            return
        try:
            open_with_webview(base)
        except ImportError:
            print("pywebview not installed — opening browser windows instead.")
            print('Install with: pip install -e ".[desktop]"')
            open_with_browser(base)
            if server:
                server.wait()
    finally:
        if server and server.poll() is None:
            server.terminate()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Launch toolgate agent/tools as desktop apps")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-ollama", action="store_true", help="Do not launch Ollama app")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Force browser tabs instead of native windows",
    )
    args = parser.parse_args(argv)
    launch(
        host=args.host,
        port=args.port,
        open_ollama=not args.no_ollama,
        force_browser=args.browser,
    )


if __name__ == "__main__":
    main()
