"""Child entrypoint: open Agent + Tools native windows."""

from __future__ import annotations

import sys


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    try:
        import webview
    except ImportError:
        import webbrowser
        import time

        webbrowser.open(f"{base}/lab/agent")
        time.sleep(0.3)
        webbrowser.open(f"{base}/lab/tools")
        return

    webview.create_window(
        "toolgate · Agent Desktop",
        f"{base}/lab/agent",
        width=540,
        height=820,
        x=40,
        y=40,
    )
    webview.create_window(
        "toolgate · Tools Desktop",
        f"{base}/lab/tools",
        width=540,
        height=820,
        x=620,
        y=40,
    )
    webview.start()


if __name__ == "__main__":
    main()
