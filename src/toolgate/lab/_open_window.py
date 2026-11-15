"""Open a single companion desktop window (agent or tools)."""

from __future__ import annotations

import sys


def main() -> None:
    kind = (sys.argv[1] if len(sys.argv) > 1 else "agent").lower()
    base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
    if kind not in {"agent", "tools"}:
        kind = "agent"

    title = "toolgate · Agent Desktop" if kind == "agent" else "toolgate · Tools Desktop"
    path = "/lab/agent" if kind == "agent" else "/lab/tools"
    x = 40 if kind == "agent" else 620

    try:
        import webview
    except ImportError:
        import webbrowser

        webbrowser.open(f"{base}{path}")
        return

    webview.create_window(title, f"{base}{path}", width=540, height=820, x=x, y=40)
    webview.start()


if __name__ == "__main__":
    main()
