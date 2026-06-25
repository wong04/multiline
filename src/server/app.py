"""FastAPI app: room REST endpoints, the live-match WebSocket, matchmaking, and
static serving.

The engine is the single source of truth — clients send intended moves, the server
validates them with the engine and broadcasts the resulting state to everyone in the
room. The browser never needs its own copy of the rules.

State (rooms, connections, queue) is in-process, so run a SINGLE replica. Idle
WebSockets are kept alive by uvicorn's protocol-level ping (see start command).
"""

import asyncio
import secrets
from contextlib import asynccontextmanager, suppress
from itertools import count
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..engine import Config, IllegalMove
from .matchmaking import QueueManager
from .rooms import Room, RoomLimit, RoomRegistry
from .schemas import CreateRoom

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
QUICKMATCH_CONFIG = Config(
	size=10, win_length=5, max_timelines=4, allow_branch=True,
	cross_win_length=4, cross_win_mode="union",
)
SWEEP_INTERVAL_SECONDS = 60

registry = RoomRegistry()
queue = QueueManager()
_conn_ids = count(1)
_connections: dict[str, dict[int, WebSocket]] = {}  # code -> {conn_id: WebSocket}
_room_locks: dict[str, asyncio.Lock] = {}  # code -> lock serializing moves/AI per room

# Errors expected when sending to a socket that's closing or already gone.
_SEND_ERRORS = (WebSocketDisconnect, RuntimeError, ConnectionError)


def _room_lock(code: str) -> asyncio.Lock:
	lock = _room_locks.get(code)
	if lock is None:
		lock = asyncio.Lock()
		_room_locks[code] = lock
	return lock


@asynccontextmanager
async def lifespan(app: FastAPI):
	sweeper = asyncio.create_task(_sweep_loop())
	yield
	sweeper.cancel()
	with suppress(asyncio.CancelledError):
		await sweeper


app = FastAPI(title="Multiline", lifespan=lifespan)


async def _sweep_loop() -> None:
	while True:
		await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
		active = {code for code, conns in _connections.items() if conns}
		registry.sweep(active)


@app.get("/healthz")
def healthz():
	return {"status": "ok"}


@app.post("/api/rooms")
def create_room(body: CreateRoom):
	try:
		room = registry.create(body.config.to_engine(), body.mode, body.aiDifficulty)
	except RoomLimit as exc:
		return JSONResponse({"error": str(exc)}, status_code=503)
	return {"code": room.code, "mode": room.mode}


@app.get("/api/rooms/{code}")
def room_info(code: str):
	room = registry.get(code)
	if room is None:
		return JSONResponse({"error": "no such room"}, status_code=404)
	return {"code": room.code, "mode": room.mode, "state": room.game.to_dict()}


def _state_message(room: Room) -> dict:
	return {"type": "state", **room.game.to_dict()}


async def _broadcast(code: str) -> None:
	room = registry.get(code)
	if room is None:
		return
	message = _state_message(room)
	for ws in list(_connections.get(code, {}).values()):
		with suppress(*_SEND_ERRORS):
			await ws.send_json(message)


def _token(websocket: WebSocket) -> str:
	return websocket.query_params.get("token") or secrets.token_hex(8)


@app.websocket("/ws/queue")
async def queue_socket(websocket: WebSocket):
	await websocket.accept()
	token = _token(websocket)
	partner = queue.join(token, websocket)
	if partner is None:
		await websocket.send_json({"type": "waiting"})
		try:
			while True:
				await websocket.receive_text()
		except WebSocketDisconnect:
			pass
		finally:
			queue.leave(websocket)
		return

	_, partner_ws = partner
	try:
		room = registry.create(QUICKMATCH_CONFIG, "online")
	except RoomLimit as exc:
		err = {"type": "error", "message": str(exc)}
		with suppress(*_SEND_ERRORS):
			await partner_ws.send_json(err)
		await websocket.send_json(err)
		return
	matched = {"type": "matched", "code": room.code}
	with suppress(*_SEND_ERRORS):
		await partner_ws.send_json(matched)
		await partner_ws.close()
	await websocket.send_json(matched)
	await websocket.close()


@app.websocket("/ws/{code}")
async def game_socket(websocket: WebSocket, code: str):
	room = registry.get(code)
	if room is None:
		await websocket.close(code=4404)
		return
	await websocket.accept()
	token = _token(websocket)
	conn_id = next(_conn_ids)
	seat = room.add_player(token)
	_connections.setdefault(code, {})[conn_id] = websocket
	await websocket.send_json(
		{"type": "joined", "seat": seat.value if seat else None, "mode": room.mode}
	)
	await _broadcast(code)
	try:
		while True:
			try:
				msg = await websocket.receive_json()
			except (ValueError, TypeError):
				await websocket.send_json({"type": "error", "message": "invalid message"})
				continue
			if not isinstance(msg, dict):
				await websocket.send_json({"type": "error", "message": "invalid message"})
				continue
			# Serialize per room so a move and the AI reply can't interleave with another
			# connection's message (e.g. a second tab) mutating the same game.
			async with _room_lock(code):
				try:
					room.apply(token, msg)
				except IllegalMove as exc:
					await websocket.send_json({"type": "error", "message": str(exc)})
					continue
				if room.is_ai_turn():
					await asyncio.to_thread(room.play_ai)
			await _broadcast(code)
	except WebSocketDisconnect:
		pass
	finally:
		conns = _connections.get(code)
		if conns is not None:
			conns.pop(conn_id, None)
			if not conns:
				_connections.pop(code, None)
				_room_locks.pop(code, None)


# Static front end mounted last so it doesn't shadow the API/WS routes above.
if WEB_DIR.is_dir():
	app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
