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


def test_cross_win_length_shorter_than_in_board():
	# With cross_win_length=3, a 3-step cross-timeline diagonal wins...
	tls = [board((0, 0, A)), board((1, 1, A)), board((2, 2, A))]
	win = find_winning_line(tls, size=5, win_length=4, cross_win_length=3)
	assert win is not None and len({c[2] for c in win.cells}) == 3
	# ...but an in-board line of 3 does NOT (in-board still needs win_length=4).
	tl = board((0, 0, A), (1, 0, A), (2, 0, A))
	assert find_winning_line([tl], size=5, win_length=4, cross_win_length=3) is None


def test_cross_timeline_needs_adjacent_timelines():
	# same diagonal but a gap in timeline index breaks the run
	tls = [
		board((0, 0, A)),
		board(),  # empty timeline interrupts
		board((2, 2, A)),
		board((3, 3, A)),
	]
	assert find_winning_line(tls, size=5, win_length=4) is None


# ---- union mode (V1): diagonal of cross_len cells held in ANY timeline, ≥2 timelines ----
def test_union_diagonal_any_timeline_order_wins():
	# diagonal (0,0),(1,1),(2,2),(3,3) but scattered across timelines in no particular order
	tls = [
		board((0, 0, A), (3, 3, A)),  # TL0 holds 2 of the 4
		board((1, 1, A)),
		board((2, 2, A)),
	]
	win = find_winning_line(tls, size=5, win_length=4, cross_win_length=4, cross_win_mode="union")
	assert win is not None and win.player is A
	assert {(c[0], c[1]) for c in win.cells} == {(0, 0), (1, 1), (2, 2), (3, 3)}
	assert len({c[2] for c in win.cells}) >= 2  # genuinely spans timelines


def test_union_all_in_one_timeline_is_not_a_cross_win():
	# a full diagonal of 4 sitting in a single board is an in-board win, not a cross win;
	# with in-board win_length=5 it shouldn't count at all here.
	tls = [board((0, 0, A), (1, 1, A), (2, 2, A), (3, 3, A)), board()]
	assert find_winning_line(tls, size=6, win_length=5, cross_win_length=4, cross_win_mode="union") is None


def test_union_needs_full_diagonal():
	tls = [board((0, 0, A)), board((1, 1, A)), board((2, 2, A))]  # only 3 of 4 cells
	assert find_winning_line(tls, size=6, win_length=5, cross_win_length=4, cross_win_mode="union") is None


# ---- distinct mode (V2): each diagonal cell in a DISTINCT timeline ----
def test_distinct_diagonal_four_distinct_timelines_wins():
	tls = [board((0, 0, A)), board((2, 2, A)), board((1, 1, A)), board((3, 3, A))]  # any order
	win = find_winning_line(tls, size=5, win_length=4, cross_win_length=4, cross_win_mode="distinct")
	assert win is not None and len({c[2] for c in win.cells}) == 4


def test_distinct_fails_without_enough_timelines():
	# the 4 diagonal cells exist but only across 2 timelines — no distinct assignment of 4
	tls = [board((0, 0, A), (2, 2, A)), board((1, 1, A), (3, 3, A))]
	assert find_winning_line(tls, size=5, win_length=4, cross_win_length=4, cross_win_mode="distinct") is None
	# union, by contrast, accepts the same position
	assert find_winning_line(tls, size=5, win_length=4, cross_win_length=4, cross_win_mode="union") is not None
