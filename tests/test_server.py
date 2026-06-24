import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.server.app import app

client = TestClient(app)

FULL = {"size": 5, "winLength": 4, "maxTimelines": 4, "allowBranch": True}


def make_room(mode, config=None, ai_difficulty="normal"):
	body = {"mode": mode, "config": config or FULL, "aiDifficulty": ai_difficulty}
	r = client.post("/api/rooms", json=body)
	assert r.status_code == 200, r.text
	return r.json()["code"]


# ---------- REST ----------
def test_healthz():
	assert client.get("/healthz").json() == {"status": "ok"}


def test_create_and_lookup_room():
	code = make_room("hotseat")
	info = client.get(f"/api/rooms/{code}")
	assert info.status_code == 200 and info.json()["mode"] == "hotseat"


def test_missing_room_is_404():
	assert client.get("/api/rooms/NOPE1").status_code == 404


def test_invalid_config_rejected():
	bad_size = client.post("/api/rooms", json={"mode": "online", "config": {**FULL, "size": 1}})
	assert bad_size.status_code == 422
	unwinnable = client.post("/api/rooms", json={"mode": "online", "config": {**FULL, "size": 5, "winLength": 6}})
	assert unwinnable.status_code == 422
	bad_mode = client.post("/api/rooms", json={"mode": "bogus", "config": FULL})
	assert bad_mode.status_code == 422


# ---------- WebSocket ----------
def test_connect_to_missing_room_is_rejected():
	with pytest.raises(WebSocketDisconnect):
		with client.websocket_connect("/ws/NOPE1") as ws:
			ws.receive_json()


def test_hotseat_place_relays_state():
	code = make_room("hotseat")
	with client.websocket_connect(f"/ws/{code}") as ws:
		assert ws.receive_json()["type"] == "joined"
		ws.receive_json()
		ws.send_json({"type": "place", "timeline": 0, "x": 2, "y": 3})
		state = ws.receive_json()
		assert {"x": 2, "y": 3, "player": "A", "inherited": False} in state["timelines"][0]
		assert state["current"] == "B"


def test_malformed_message_does_not_kill_socket():
	code = make_room("hotseat")
	with client.websocket_connect(f"/ws/{code}") as ws:
		ws.receive_json()
		ws.receive_json()
		ws.send_text("{not json")
		assert ws.receive_json() == {"type": "error", "message": "invalid message"}
		# socket still usable afterwards
		ws.send_json({"type": "place", "timeline": 0, "x": 0, "y": 0})
		assert ws.receive_json()["type"] == "state"


def test_online_enforces_seats_and_turns():
	code = make_room("online")
	with client.websocket_connect(f"/ws/{code}?token=a") as a:
		assert a.receive_json()["seat"] == "A"
		a.receive_json()
		with client.websocket_connect(f"/ws/{code}?token=b") as b:
			assert b.receive_json()["seat"] == "B"
			b.receive_json()
			a.receive_json()
			a.send_json({"type": "place", "timeline": 0, "x": 0, "y": 0})
			a.receive_json()
			b.receive_json()
			a.send_json({"type": "place", "timeline": 0, "x": 1, "y": 1})
			err = a.receive_json()
			assert err["type"] == "error" and "turn" in err["message"]


def test_third_online_connection_spectates():
	code = make_room("online")
	with client.websocket_connect(f"/ws/{code}?token=a") as a:
		a.receive_json(); a.receive_json()
		with client.websocket_connect(f"/ws/{code}?token=b") as b:
			b.receive_json(); b.receive_json(); a.receive_json()
			with client.websocket_connect(f"/ws/{code}?token=c") as c:
				assert c.receive_json()["seat"] is None


def test_online_reset_gated_until_game_over():
	code = make_room("online")
	with client.websocket_connect(f"/ws/{code}?token=a") as a:
		a.receive_json(); a.receive_json()
		with client.websocket_connect(f"/ws/{code}?token=b") as b:
			b.receive_json(); b.receive_json(); a.receive_json()
			a.send_json({"type": "reset"})
			err = a.receive_json()
			assert err["type"] == "error" and "reset" in err["message"]


def test_seats_persist_by_token_across_reconnect():
	code = make_room("online")
	a = client.websocket_connect(f"/ws/{code}?token=alice")
	aws = a.__enter__()
	assert aws.receive_json()["seat"] == "A"
	aws.receive_json()
	c = client.websocket_connect(f"/ws/{code}?token=carol")
	cws = c.__enter__()
	assert cws.receive_json()["seat"] == "B"
	aws.receive_json()
	a.__exit__(None, None, None)  # alice disconnects, but token keeps seat A

	d = client.websocket_connect(f"/ws/{code}?token=dave")
	dws = d.__enter__()
	assert dws.receive_json()["seat"] is None  # A still reserved for alice
	d.__exit__(None, None, None)

	a2 = client.websocket_connect(f"/ws/{code}?token=alice")
	a2ws = a2.__enter__()
	assert a2ws.receive_json()["seat"] == "A"  # restored
	a2.__exit__(None, None, None)
	c.__exit__(None, None, None)


def test_ai_responds_after_human_move():
	code = make_room("ai")
	with client.websocket_connect(f"/ws/{code}?token=human") as ws:
		assert ws.receive_json()["seat"] == "A"
		ws.receive_json()
		ws.send_json({"type": "place", "timeline": 0, "x": 3, "y": 3})
		state = ws.receive_json()
		assert state["type"] == "state"
		assert state["current"] == "A"  # AI (B) already replied
		b_stones = [s for tl in state["timelines"] for s in tl if s["player"] == "B"]
		assert len(b_stones) == 1


def test_quickmatch_pairs_two_clients():
	with client.websocket_connect("/ws/queue?token=p1") as a:
		assert a.receive_json() == {"type": "waiting"}
		with client.websocket_connect("/ws/queue?token=p2") as b:
			amsg = a.receive_json()
			bmsg = b.receive_json()
			assert amsg["type"] == "matched"
			assert amsg["code"] == bmsg["code"]


def test_reset_clears_board():
	code = make_room("hotseat")
	with client.websocket_connect(f"/ws/{code}") as ws:
		ws.receive_json(); ws.receive_json()
		ws.send_json({"type": "place", "timeline": 0, "x": 0, "y": 0})
		ws.receive_json()
		ws.send_json({"type": "reset"})
		state = ws.receive_json()
		assert state["timelines"] == [[]] and state["current"] == "A"
