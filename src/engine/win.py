"""Win detection over the (x, y, L) lattice.

A winning line is `win_length` same-colour stones in a straight line through the
lattice, with direction vector (dx, dy, dl) where each component is in {-1, 0, 1},
not all zero, and at least one of dx/dy is non-zero. Requiring spatial movement
excludes the degenerate "same cell straight across timelines" line that branch
copying would otherwise make trivial.
"""

from dataclasses import dataclass

from .player import Player

Cell = tuple[int, int, int]  # (x, y, timeline_index)


@dataclass(frozen=True)
class WinningLine:
	player: Player
	cells: list[Cell]


def _canonical_directions() -> list[tuple[int, int, int]]:
	"""One direction per ± pair; spatial movement required (dx or dy non-zero)."""
	dirs = []
	for dx in (-1, 0, 1):
		for dy in (-1, 0, 1):
			for dl in (-1, 0, 1):
				if dx == 0 and dy == 0:
					continue
				v = (dx, dy, dl)
				if v > (-dx, -dy, -dl):  # keep exactly one of {v, -v}
					dirs.append(v)
	return dirs


_DIRECTIONS = _canonical_directions()


def find_winning_line(
	timelines: list[dict[tuple[int, int], Player]],
	size: int,
	win_length: int,
	cross_win_length: int | None = None,
	cross_win_mode: str = "step",
) -> WinningLine | None:
	"""In-board lines (dl == 0) need `win_length`. Cross-timeline wins use `cross_win_length`
	stones, detected per `cross_win_mode` ("step" | "union" | "distinct")."""
	cross_len = cross_win_length or win_length
	if cross_win_mode == "step":
		return _find_step(timelines, size, win_length, cross_len)
	# union / distinct: in-board straight lines still win the normal way...
	line = _find_in_board(timelines, size, win_length)
	if line is not None:
		return line
	return _find_cross_diagonal(timelines, size, cross_len, cross_win_mode)


def _find_step(timelines, size, win_length, cross_len) -> WinningLine | None:
	count = len(timelines)
	for origin_l, board in enumerate(timelines):
		for (x, y), player in board.items():
			for dx, dy, dl in _DIRECTIONS:
				target = win_length if dl == 0 else cross_len
				cells = [(x, y, origin_l)]
				for k in range(1, target):
					nx, ny, nl = x + dx * k, y + dy * k, origin_l + dl * k
					if not (0 <= nx < size and 0 <= ny < size and 0 <= nl < count):
						break
					if timelines[nl].get((nx, ny)) != player:
						break
					cells.append((nx, ny, nl))
				if len(cells) == target:
					return WinningLine(player, cells)
	return None


def _find_in_board(timelines, size, win_length) -> WinningLine | None:
	"""Straight lines within a single board (rows, columns, diagonals)."""
	for l, board in enumerate(timelines):
		for (x, y), player in board.items():
			for dx, dy, dl in _DIRECTIONS:
				if dl != 0:
					continue
				cells = [(x, y, l)]
				for k in range(1, win_length):
					nx, ny = x + dx * k, y + dy * k
					if not (0 <= nx < size and 0 <= ny < size):
						break
					if board.get((nx, ny)) != player:
						break
					cells.append((nx, ny, l))
				if len(cells) == win_length:
					return WinningLine(player, cells)
	return None


# Diagonal directions only, one per ± pair, for cross-timeline diagonal wins.
_DIAGONALS = [(1, 1), (1, -1)]


def _find_cross_diagonal(timelines, size, cross_len, mode) -> WinningLine | None:
	"""A diagonal of `cross_len` cells where the player's planets (in any timeline) fill it,
	spanning ≥2 timelines. "union": cells may reuse timelines. "distinct": each diagonal cell
	must map to a distinct timeline (any order)."""
	count = len(timelines)
	for player in (Player.A, Player.B):
		for dx, dy in _DIAGONALS:
			for sx in range(size):
				for sy in range(size):
					ex, ey = sx + dx * (cross_len - 1), sy + dy * (cross_len - 1)
					if not (0 <= ex < size and 0 <= ey < size):
						continue
					cells = [(sx + dx * k, sy + dy * k) for k in range(cross_len)]
					tl_sets = [
						[l for l in range(count) if timelines[l].get((cx, cy)) is player]
						for (cx, cy) in cells
					]
					if any(not s for s in tl_sets):
						continue  # some diagonal cell not held anywhere
					# purely in-board (one timeline holds all) is not a cross win — skip it
					if any(all(l in s for s in tl_sets) for l in range(count)):
						continue
					assigned = (
						_assign_any(tl_sets) if mode == "union"
						else _assign_distinct(tl_sets)
					)
					if assigned is None:
						continue
					return WinningLine(player, [(cx, cy, l) for (cx, cy), l in zip(cells, assigned)])
	return None


def _assign_any(tl_sets) -> list[int] | None:
	"""Pick a timeline per cell using ≥2 distinct timelines overall (cells may reuse)."""
	pick = [s[0] for s in tl_sets]
	if len(set(pick)) >= 2:
		return pick
	# all defaulted to the same timeline; force one cell onto a different timeline if possible
	for i, s in enumerate(tl_sets):
		other = next((l for l in s if l != pick[0]), None)
		if other is not None:
			pick[i] = other
			return pick
	return None


def _assign_distinct(tl_sets) -> list[int] | None:
	"""Backtracking system-of-distinct-representatives: each cell a unique timeline."""
	used: set[int] = set()
	result: list[int] = []

	def solve(i: int) -> bool:
		if i == len(tl_sets):
			return True
		for l in tl_sets[i]:
			if l in used:
				continue
			used.add(l); result.append(l)
			if solve(i + 1):
				return True
			used.discard(l); result.pop()
		return False

	return result if solve(0) else None
