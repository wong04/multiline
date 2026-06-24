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
) -> WinningLine | None:
	count = len(timelines)
	for origin_l, board in enumerate(timelines):
		for (x, y), player in board.items():
			for dx, dy, dl in _DIRECTIONS:
				cells = [(x, y, origin_l)]
				for k in range(1, win_length):
					nx, ny, nl = x + dx * k, y + dy * k, origin_l + dl * k
					if not (0 <= nx < size and 0 <= ny < size and 0 <= nl < count):
						break
					if timelines[nl].get((nx, ny)) != player:
						break
					cells.append((nx, ny, nl))
				if len(cells) == win_length:
					return WinningLine(player, cells)
	return None
