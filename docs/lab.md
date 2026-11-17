# toolgate interface

An open-source agent (Ollama) proposes tool calls. **toolgate** mediates execution before any side effects.

## Prerequisites

- Python 3.12+ and this repo’s `.venv`
- [Ollama](https://ollama.com) installed and running
- A chat model that supports tools (recommended: `qwen2.5:3b-instruct`)

```powershell
ollama serve
ollama pull qwen2.5:3b-instruct
```

## Start as desktop apps

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,serve,desktop]"
.\.venv\Scripts\python.exe -m toolgate.lab.desktop
```

This opens three native windows:

1. **Control** — workflow visualization (`/`)
2. **Agent Desktop** — live Ollama proposals (`/lab/agent`)
3. **Tools Desktop** — ALLOW/DENY + tool results + store (`/lab/tools`)

Clicking **Run live agent → gateway**:

1. Closes any open Agent/Tools windows
2. Opens **Agent Desktop** and shows LLM thinking → tool decision
3. Opens **Tools Desktop** and shows SUCCESS or DENIED
4. Animates the main workflow packet path (no separate event-timeline list)

## Start the interface in a browser

```powershell
.\.venv\Scripts\python.exe -m uvicorn toolgate.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/

1. Stay on **Live Lab (Ollama)**
2. Pick a preset (safe or attack)
3. Keep mode on **gateway**
4. Click **Run live agent → gateway**

The page animates the packet through principal → Ollama agent → policy → audit → tools/blocked, and shows the live event timeline.

## What is “real”

| Layer | Implementation |
| --- | --- |
| Agent | Ollama native `tools` API |
| Tools | `SimulatedRuntime` against seeded SQLite store |
| Gate | Same policy engine as evaluation (`gateway` mode) |
| UI | Workflow viz + timeline on port 8000 |

## API

- `GET /lab/status` — Ollama reachability, models, presets, and principals. Seed access tokens are not included.
- `POST /reset` — clears the store, reseeds it, and drops open sessions.
- `POST /lab/session` — `{ user_id }` returns a session. Send it as `Authorization: Bearer`.
- `POST /lab/run` — the bearer token identifies the caller. A principal in the body is ignored.

The interface keeps its store in `data/runtime/toolgate.sqlite`. Measured cases use a fresh in-memory store instead.

If the model returns no tool call, a preset can fall back to its scripted call and the interface labels that fallback. A tool payload that does not parse is denied and is not executed.

## Companion pages

| URL | Purpose |
| --- | --- |
| `/lab/agent` | Agent desktop surface (task, proposal, raw Ollama message) |
| `/lab/tools` | Tools desktop surface (decision, results, store snapshot) |
| `GET /lab/latest` | Last lab run JSON polled by the desktop apps |
| `POST /lab/desktop` | Spawn Agent + Tools native windows |
