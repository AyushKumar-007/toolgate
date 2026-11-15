"""Spawn / close Agent + Tools desktop companion windows."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

_procs: dict[str, subprocess.Popen | None] = {"agent": None, "tools": None}
_MARKER = "_open_window.py"
_TITLES = {
    "agent": "toolgate · Agent Desktop",
    "tools": "toolgate · Tools Desktop",
}


def _kill_tree(pid: int) -> None:
    """Kill a process and all children (Windows-safe)."""
    if pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.kill(pid, 15)
    except OSError:
        pass


def _run_ps(script: str, timeout: float = 12) -> str:
    if os.name != "nt":
        return ""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return (result.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _kill_by_cmdline(match: str) -> list[int]:
    """Kill processes whose command line contains match."""
    killed: list[int] = []
    if os.name != "nt":
        try:
            result = subprocess.run(
                ["pgrep", "-f", match],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in (result.stdout or "").splitlines():
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    _kill_tree(pid)
                    killed.append(pid)
        except OSError:
            pass
        return killed

    pattern = match.replace(".", "\\.").replace(" ", "\\s+")
    script = (
        "$ids = @(); "
        "Get-CimInstance Win32_Process | Where-Object { "
        f"$_.CommandLine -and ($_.CommandLine -match '{pattern}') "
        "} | ForEach-Object { $ids += $_.ProcessId; "
        "taskkill /PID $_.ProcessId /T /F 2>$null | Out-Null }; "
        "$ids -join ','"
    )
    raw = _run_ps(script)
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                killed.append(int(part))
    return killed


def _kill_by_window_title(title: str) -> list[int]:
    """Kill processes that own a main window with the given title.

    pywebview/WebView2 hosts are not always children of the launcher PID, so
    title matching is required to prevent stacked companion windows.
    """
    if os.name != "nt" or not title:
        return []
    # Escape single quotes for PowerShell string literal.
    safe = title.replace("'", "''")
    script = (
        "$ids = @(); "
        "Get-Process | Where-Object { "
        f"$_.MainWindowTitle -eq '{safe}' "
        "} | ForEach-Object { $ids += $_.Id; "
        "Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }; "
        "$ids -join ','"
    )
    raw = _run_ps(script)
    killed: list[int] = []
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                killed.append(int(part))
    return killed


def _kill_kind(kind: str) -> list[int]:
    """Kill tracked + orphaned hosts for one companion kind."""
    killed: list[int] = []
    proc = _procs.get(kind)
    if proc is not None:
        if proc.poll() is None:
            _kill_tree(proc.pid)
            killed.append(proc.pid)
        _procs[kind] = None
    killed.extend(_kill_by_cmdline(f"{_MARKER} {kind}"))
    title = _TITLES.get(kind)
    if title:
        killed.extend(_kill_by_window_title(title))
    return killed


def close_companions() -> dict:
    """Force-close both Agent and Tools windows, including orphans."""
    closed: list[str] = []
    orphans: list[int] = []
    for kind in ("agent", "tools"):
        pids = _kill_kind(kind)
        if pids:
            closed.append(kind)
            orphans.extend(pids)
    # Sweep any leftover companion hosts / titled windows.
    orphans.extend(_kill_by_cmdline(_MARKER))
    for title in _TITLES.values():
        orphans.extend(_kill_by_window_title(title))
    time.sleep(0.7)
    return {"status": "closed", "closed": closed, "orphans_killed": orphans}


def spawn_window(
    kind: str,
    base_url: str = "http://127.0.0.1:8000",
    *,
    force: bool = True,
) -> dict:
    """Open one companion window. Clears prior windows of the same kind first."""
    if kind not in {"agent", "tools"}:
        raise ValueError("kind must be 'agent' or 'tools'")

    if force:
        _kill_kind(kind)
        time.sleep(0.35)
    else:
        proc = _procs.get(kind)
        if proc is not None and proc.poll() is None:
            return {"status": "already_open", "kind": kind, "pid": proc.pid}

    script = Path(__file__).with_name("_open_window.py")
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    proc = subprocess.Popen(
        [sys.executable, str(script), kind, base_url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    _procs[kind] = proc
    return {"status": "spawning", "kind": kind, "pid": proc.pid, "base_url": base_url}


def spawn_companion_windows(base_url: str = "http://127.0.0.1:8000") -> dict:
    """Open both windows (used by full desktop launcher)."""
    close_companions()
    agent = spawn_window("agent", base_url, force=True)
    tools = spawn_window("tools", base_url, force=True)
    return {"status": "spawning", "agent": agent, "tools": tools}
