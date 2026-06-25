"""Multiverse board state and move rules for Multiline.

v1 is parallel-timelines-only: state is an ordered list of small grids (timelines).
A move is either a placement on an existing timeline or a branch that copies an
existing timeline and places into the copy.
"""

from __future__ import annotations

from dataclasses import dataclass

from .player import Player
from .win import find_winning_line


class IllegalMove(Exception):
	"""Raised when a requested move violates the rules."""


@dataclass(frozen=True)
class Config:
	size: int = 5
	win_length: int = 4
	max_timelines: int = 4
	allow_branch: bool = True
	# A line that steps across timelines may win with fewer stones than an in-board line,
	# so the extra dimension is worth using. None => same as win_length (no cross discount).
	cross_win_length: int | None = None
	# Whether a fork copies the opponent's planets too. True keeps the new timeline
	# contestable (they can block across boards) — this is what gives games defensive
	# depth. False is an asymmetric "fresh front" (fast but shallow).
	fork_keep_opponent: bool = True
	# How a cross-timeline line wins:
	#   "step"     — straight line stepping through consecutive timelines (dl=±1 each step)
	#   "union"    — a diagonal of cross_len cells, each occupied in some timeline, ≥2 timelines
	#   "distinct" — a diagonal of cross_len cells, each in a distinct timeline (any order)
	cross_win_mode: str = "step"

	@property
	def cross_len(self) -> int:
		return self.cross_win_length or self.win_length


class Game:
	def __init__(self, config: Config | None = None):
		self.config = config or Config()
		self.timelines: list[dict[tuple[int, int], Player]] = [{}]
		# Per timeline: cells that were copied in when it branched (for ghost display).
		self.inherited: list[set[tuple[int, int]]] = [set()]
		self.current: Player = Player.A
		self.winner: Player | None = None
		self.winning_line = None  # WinningLine | None, set on a winning move

	@property
	def over(self) -> bool:
		return self.winner is not None

	def _in_bounds(self, x: int, y: int) -> bool:
		return 0 <= x < self.config.size and 0 <= y < self.config.size

	def place(self, timeline: int, x: int, y: int) -> None:
		"""Place the current player's stone on an existing timeline."""
		if self.over:
			raise IllegalMove("game is already over")
		if not 0 <= timeline < len(self.timelines):
			raise IllegalMove(f"no timeline {timeline}")
		if not self._in_bounds(x, y):
			raise IllegalMove(f"({x}, {y}) is off the board")
		if (x, y) in self.timelines[timeline]:
			raise IllegalMove(f"({x}, {y}) is occupied in timeline {timeline}")
		self.timelines[timeline][(x, y)] = self.current
		self._after_move()

	def branch(self, source: int, x: int, y: int) -> None:
		"""Fork `source` into a fresh timeline carrying only the current player's planets,
		then place their stone. Dropping the opponent's stones makes the fork a new front
		where the brancher is ahead — that's what makes forking worth a tempo."""
		if self.over:
			raise IllegalMove("game is already over")
		if not self.config.allow_branch:
			raise IllegalMove("branching is disabled")
		if len(self.timelines) >= self.config.max_timelines:
			raise IllegalMove("timeline limit reached")
		if not 0 <= source < len(self.timelines):
			raise IllegalMove(f"no timeline {source}")
		if not self._in_bounds(x, y):
			raise IllegalMove(f"({x}, {y}) is off the board")
		src = self.timelines[source]
		carried = dict(src) if self.config.fork_keep_opponent else {
			pos: p for pos, p in src.items() if p is self.current
		}
		if (x, y) in carried:
			raise IllegalMove(f"({x}, {y}) is occupied in timeline {source}")
		inherited_keys = set(carried.keys())
		new_timeline = dict(carried)
		new_timeline[(x, y)] = self.current
		self.timelines.append(new_timeline)
		self.inherited.append(inherited_keys)
		self._after_move()

	def copy(self) -> Game:
		"""A deep-enough copy for AI search (shares the immutable Config)."""
		clone = Game(self.config)
		clone.timelines = [dict(board) for board in self.timelines]
		clone.inherited = [set(keys) for keys in self.inherited]
		clone.current = self.current
		clone.winner = self.winner
		clone.winning_line = self.winning_line
		return clone

	def _after_move(self) -> None:
		line = find_winning_line(
			self.timelines, self.config.size, self.config.win_length, self.config.cross_len,
			self.config.cross_win_mode,
		)
		if line is not None:
			self.winner = line.player
			self.winning_line = line
			return
		self.current = self.current.other

	def to_dict(self) -> dict:
		return {
			"config": {
				"size": self.config.size,
				"winLength": self.config.win_length,
				"crossWinLength": self.config.cross_len,
				"crossWinMode": self.config.cross_win_mode,
				"maxTimelines": self.config.max_timelines,
				"allowBranch": self.config.allow_branch,
			},
			"timelines": [
				[
					{
						"x": x,
						"y": y,
						"player": p.value,
						"inherited": (x, y) in self.inherited[l],
					}
					for (x, y), p in board.items()
				]
				for l, board in enumerate(self.timelines)
			],
			"current": self.current.value,
			"winner": self.winner.value if self.winner else None,
			"winningLine": (
				[{"x": x, "y": y, "l": l} for (x, y, l) in self.winning_line.cells]
				if self.winning_line
				else None
			),
		}
