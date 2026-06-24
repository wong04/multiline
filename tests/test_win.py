from src.engine.board import Player
from src.engine.win import find_winning_line


def board(*stones):
	"""Build one timeline dict from (x, y, player) tuples."""
	return {(x, y): p for (x, y, p) in stones}


A, B = Player.A, Player.B


def test_horizontal_line_within_board():
	tl = board((0, 0, A), (1, 0, A), (2, 0, A), (3, 0, A))
	win = find_winning_line([tl], size=5, win_length=4)
	assert win is not None
	assert win.player is A
	assert (0, 0, 0) in win.cells and (3, 0, 0) in win.cells


def test_diagonal_line_within_board():
	tl = board((0, 0, B), (1, 1, B), (2, 2, B), (3, 3, B))
	win = find_winning_line([tl], size=5, win_length=4)
	assert win is not None and win.player is B


def test_no_win_when_broken_by_opponent():
	tl = board((0, 0, A), (1, 0, A), (2, 0, B), (3, 0, A), (4, 0, A))
	assert find_winning_line([tl], size=5, win_length=4) is None


def test_cross_timeline_diagonal_wins():
	# stone steps (x,y) by +1 and timeline by +1 each step
	tls = [
		board((0, 0, A)),
		board((1, 1, A)),
		board((2, 2, A)),
		board((3, 3, A)),
	]
	win = find_winning_line(tls, size=5, win_length=4)
	assert win is not None and win.player is A
	assert {c[2] for c in win.cells} == {0, 1, 2, 3}


def test_same_cell_across_timelines_does_not_win():
	# the degenerate case branch-copying would create: identical cell, no spatial move
	tls = [board((2, 2, A)) for _ in range(4)]
	assert find_winning_line(tls, size=5, win_length=4) is None


def test_cross_timeline_needs_adjacent_timelines():
	# same diagonal but a gap in timeline index breaks the run
	tls = [
		board((0, 0, A)),
		board(),  # empty timeline interrupts
		board((2, 2, A)),
		board((3, 3, A)),
	]
	assert find_winning_line(tls, size=5, win_length=4) is None
