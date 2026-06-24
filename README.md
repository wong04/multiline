# Multiline

A competitive multiverse line game inspired by *5D Chess with Multiverse Time Travel*.

It's Gomoku played across parallel timelines you can spawn. Win by getting N stones in
a row **within a board** or **stepping diagonally across adjacent timelines**. Branching
copies a timeline's stones forward (the "time travel" feel); a single uniform win rule
requires every winning line to move through space, so trivial same-cell copies never win.

## Architecture
- `src/engine/` — pure-Python rules (no web deps). The single source of truth.
  - `player.py`, `board.py`, `win.py` — state, moves, win detection.
  - `ai.py` — depth-limited alpha-beta opponent (easy/normal/hard).
- `src/server/` — FastAPI: room REST + live-match WebSocket + quick-match queue + static.
  - `rooms.py` — in-memory rooms; seats keyed by a stable client token (reconnect-safe).
  - `matchmaking.py` — quick-match queue.
- `src/web/` — HTML5 canvas + vanilla JS front end (hotseat, online, and — after the
  frontend rework — AI and quick-match).

The server validates every move with the engine and broadcasts state to the room, so the
browser never needs its own copy of the rules.

### Game modes
- **hotseat** — both players on one device.
- **online** — two seats (A/B) enforced; extra joiners spectate; shareable room code.
- **ai** — human is seat A, the computer plays seat B.
- **quick-match** — `/ws/queue` pairs the next two waiting players into an online room.

### Operational notes
- Room/connection/queue state is **in-process** — run a **single replica** (Railway
  `numReplicas: 1`). Move to Redis if horizontal scaling is ever needed.
- Idle rooms with no live connections are swept after ~10 min; total rooms are capped.
- Idle WebSockets stay alive via uvicorn's protocol-level ping (`--ws-ping-interval`).

## Run locally
```sh
uv sync
uv run uvicorn src.server.app:app --reload
```
Then open http://localhost:8000 — create a hotseat game to play both sides on one device,
or an online game and share the room code.

## Test
```sh
uv run pytest
```

## Deploy (Railway)
The repo ships `railway.json` and a `Procfile`. Railway builds with Nixpacks (`uv sync`)
and starts:
```
uv run uvicorn src.server.app:app --host 0.0.0.0 --port $PORT
```
The single service (`multiline`) serves the API, WebSocket, and front end — no separate
front-end host needed. Public URL: https://multiline-production.up.railway.app

### Push-to-deploy (CI)
`.github/workflows/deploy.yml` runs the tests then deploys on every push to `main` via the
Railway CLI (`railway up`), which is more reliable than Railway's native GitHub builder.
One-time setup:
1. Railway dashboard → project **multiline** → **Settings → Tokens** → create a token.
2. GitHub repo → **Settings → Secrets and variables → Actions** → add secret
   `RAILWAY_TOKEN` with that value.
3. In Railway, **disconnect** the service's native GitHub source (service → Settings →
   Source) so deploys come only from the Action and you don't get duplicate builds.

Manual deploy any time: `railway up --service multiline`.

## Rulesets (accessibility ramp)
- **Classic** — branching off; plain Gomoku. Learn the base in seconds.
- **Branching** — up to 3 timelines; learn the multiverse.
- **Full** — up to 4 timelines.
