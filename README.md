# toolgate

Policy-based runtime security gateway for applications where a language model proposes tool calls. The gateway checks identity, tenant, ownership, allowed actions, arguments, and approval tokens before any tool runs.

## Install

Python 3.12 or newer.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,serve,desktop]"
```

`desktop` installs the native window library used by the Agent and Tools windows.

## Run the interface

```powershell
.\.venv\Scripts\python.exe -m uvicorn toolgate.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/

Ollama proposes the tool call when it is running. Each preset also has a scripted fallback so the gateway can still decide if the model does not answer. Setup steps are in [docs/lab.md](docs/lab.md).

```powershell
.\scripts\setup_lab.ps1
```

Desktop windows:

```powershell
.\.venv\Scripts\python.exe -m toolgate.lab.desktop
```

## Tests and measured cases

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m eval.runner
.\.venv\Scripts\python.exe scripts\run_cases.py
```

The evaluation runner writes JSONL and metrics under `data/results/`. A saved snapshot is in [docs/results_snapshot.json](docs/results_snapshot.json). The threat catalogue is in [docs/threat-model.md](docs/threat-model.md).

## Layout

| Path | Purpose |
| --- | --- |
| `src/toolgate` | Gateway, policy, store, tools, API, and interface |
| `tests` | Unit and integration tests |
| `eval` | Case loader and three-mode runner |
| `data/cases` | Legitimate and attack cases |
| `data/synthetic` | Seed users, records, and approvals |
| `schemas` | JSON Schema for the shared models |
