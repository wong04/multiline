"""In-memory match rooms. No web framework types here so it stays unit-testable.

`mode` is "online" (two seats A/B enforced, extra joiners spectate), "hotseat" (one
client controls both sides), or "ai" (human is seat A, the computer plays seat B).

Seats are keyed by a stable client token (not the ephemeral connection), so a player
who reconnects with the same token keeps their seat.
"""

import secrets
import string
import time

from ..engine import Config, Game, IllegalMove, Player

AI_SEAT = Player.B
MAX_ROOMS = 500
ROOM_TTL_SECONDS = 600  # rooms idle with no live connections this long are swept


class RoomLimit(Exception):
	"""Raised when the server is at its room capacity."""


class Room:
	def __init__(self, code: str, config: Config, mode: str, ai_difficulty: str = "normal"):
		if mode not in ("online", "hotseat", "ai"):
			raise ValueError(f"unknown mode {mode!r}")
		self.code = code
		self.mode = mode
		self.config = config
		self.ai_difficulty = ai_difficulty
		self.game = Game(config)
		self.seats: dict[str, Player | None] = {}  # client token -> seat (None = spectator)
		self.owner_token: str | None = None  # first client to join; controls reset in ai/hotseat
		self.last_active = time.monotonic()

	def touch(self) -> None:
		self.last_active = time.monotonic()

	def add_player(self, token: str) -> Player | None:
		self.touch()
		if self.owner_token is None:
			self.owner_token = token
		if token in self.seats:
			return self.seats[token]  # reconnecting: keep the same seat
		if self.mode == "hotseat":
			self.seats[token] = None
			return None
		taken = {s for s in self.seats.values() if s is not None}
		claimable = (Player.A,) if self.mode == "ai" else (Player.A, Player.B)
		for seat in claimable:
			if seat not in taken:
				self.seats[token] = seat
				return seat
		self.seats[token] = None  # spectator
		return None

	def is_seated(self, token: str) -> bool:
		return self.seats.get(token) is not None

	def may_move(self, token: str) -> bool:
		if self.mode == "hotseat":
			return True
		return self.seats.get(token) == self.game.current

	def reset(self) -> None:
		self.game = Game(self.config)
		self.touch()

	def is_ai_turn(self) -> bool:
		return self.mode == "ai" and not self.game.over and self.game.current is AI_SEAT

	def play_ai(self) -> None:
		from ..engine.ai import choose_move

		move = choose_move(self.game, self.ai_difficulty)
		if move is None:
			return
		if move[0] == "place":
			self.game.place(move[1], move[2], move[3])
		else:
			self.game.branch(move[1], move[2], move[3])
		self.touch()

	def apply(self, token: str, msg: dict) -> None:
		"""Validate and apply a client message. Raises IllegalMove on rejection."""
		self.touch()
		kind = msg.get("type")
		if kind == "reset":
			if self.mode == "online":
				if not self.is_seated(token):
					raise IllegalMove("only seated players can reset")
				if not self.game.over:
					raise IllegalMove("can only reset after the game ends")
			# ai/hotseat have a single human controller — only the room owner may reset,
			# so a spectator/second tab can't wipe the board mid-game.
			elif token != self.owner_token:
				raise IllegalMove("only the game owner can reset")
			self.reset()
			return
		if not self.may_move(token):
			raise IllegalMove("not your turn")
		try:
			if kind == "place":
				self.game.place(int(msg["timeline"]), int(msg["x"]), int(msg["y"]))
			elif kind == "branch":
				self.game.branch(int(msg["source"]), int(msg["x"]), int(msg["y"]))
			else:
				raise IllegalMove(f"unknown move type {kind!r}")
		except (KeyError, TypeError, ValueError) as exc:
			raise IllegalMove(f"malformed move: {exc}") from exc


class RoomRegistry:
	def __init__(self, max_rooms: int = MAX_ROOMS):
		self.rooms: dict[str, Room] = {}
		self.max_rooms = max_rooms

	def create(self, config: Config, mode: str, ai_difficulty: str = "normal") -> Room:
		if len(self.rooms) >= self.max_rooms:
			raise RoomLimit("server is at capacity, please try again later")
		code = self._new_code()
		room = Room(code, config, mode, ai_difficulty)
		self.rooms[code] = room
		return room

	def get(self, code: str) -> Room | None:
		return self.rooms.get(code)

	def remove(self, code: str) -> None:
		self.rooms.pop(code, None)

	def sweep(self, active_codes: set[str], ttl: float = ROOM_TTL_SECONDS) -> list[str]:
		"""Drop rooms with no live connections that have been idle past `ttl`."""
		now = time.monotonic()
		stale = [
			code
			for code, room in self.rooms.items()
			if code not in active_codes and now - room.last_active > ttl
		]
		for code in stale:
			self.rooms.pop(code, None)
		return stale

	def _new_code(self) -> str:
		alphabet = string.ascii_uppercase + string.digits
		while True:
			code = "".join(secrets.choice(alphabet) for _ in range(5))
			if code not in self.rooms:
				return code
