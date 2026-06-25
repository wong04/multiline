import pytest

from src.engine.board import Config, Game, IllegalMove, Player

A, B = Player.A, Player.B


def test_alternates_players():
	g = Game()
	assert g.current is A
	g.place(0, 0, 0)
	assert g.current is B
	g.place(0, 1, 1)
	assert g.current is A


def test_cannot_place_on_occupied_cell():
	g = Game()
	g.place(0, 0, 0)
	with pytest.raises(IllegalMove):
		g.place(0, 0, 0)


def test_off_board_rejected():
	g = Game(Config(size=5))
	with pytest.raises(IllegalMove):
		g.place(0, 5, 0)


def test_branch_contestable_copies_whole_board():
	# Default (contestable) fork: the new timeline copies BOTH players' planets, so the
	# opponent can still defend across boards.
	g = Game()
	g.place(0, 0, 0)  # A in timeline 0
	g.place(0, 1, 1)  # B in timeline 0
	g.branch(0, 2, 2)  # A branches timeline 0 -> timeline 1, places at (2,2)
	assert len(g.timelines) == 2
	assert g.timelines[1][(0, 0)] is A  # A's stone carried (inherited echo)
	assert g.timelines[1][(1, 1)] is B  # B's stone carried too (contestable)
	assert g.timelines[1][(2, 2)] is A  # newly placed


def test_branch_asymmetric_drops_opponent():
	# With fork_keep_opponent=False, the new timeline keeps only the brancher's planets.
	g = Game(Config(fork_keep_opponent=False))
	g.place(0, 0, 0)  # A
	g.place(0, 1, 1)  # B
	g.branch(0, 2, 2)  # A
	assert g.timelines[1][(0, 0)] is A
	assert (1, 1) not in g.timelines[1]  # B's stone dropped
	assert g.timelines[1][(2, 2)] is A


def test_branch_disabled():
	g = Game(Config(allow_branch=False))
	with pytest.raises(IllegalMove):
		g.branch(0, 0, 0)


def test_timeline_cap_enforced():
	g = Game(Config(max_timelines=2))
	g.branch(0, 0, 0)  # -> 2 timelines
	with pytest.raises(IllegalMove):
		g.branch(0, 1, 1)  # would be the 3rd


def test_winning_move_ends_game_and_blocks_further_moves():
	g = Game(Config(win_length=4, max_timelines=4))
	# A builds a row on timeline 0; B plays elsewhere
	g.place(0, 0, 0)  # A
	g.place(0, 0, 4)  # B
	g.place(0, 1, 0)  # A
	g.place(0, 1, 4)  # B
	g.place(0, 2, 0)  # A
	g.place(0, 2, 4)  # B
	g.place(0, 3, 0)  # A wins
	assert g.over and g.winner is A
	with pytest.raises(IllegalMove):
		g.place(0, 4, 0)


def test_cross_timeline_win_via_play():
	# A wins on a diagonal threaded across THREE sibling timelines, where no single
	# board ever holds 3-in-a-row (both branches fork from t0, so they diverge).
	g = Game(Config(win_length=3, max_timelines=4))
	g.place(0, 0, 0)   # A: (0,0) in t0
	g.place(0, 4, 4)   # B: harmless corner
	g.branch(0, 1, 1)  # A: t1 = copy(t0) + (1,1)
	g.place(1, 0, 4)   # B
	g.branch(0, 2, 2)  # A: t2 = copy(t0) + (2,2); diagonal (0,0,t0)(1,1,t1)(2,2,t2)
	assert g.over and g.winner is A
	used_timelines = {c[2] for c in g.winning_line.cells}
	assert used_timelines == {0, 1, 2}


def test_union_cross_win_via_play():
	# Union mode: a diagonal of 4 assembled ACROSS timelines (the tutorial lesson-3 shape).
	# (1,1) lives only in t1, so completing (2,2) can't be an in-board 4 — only a cross win.
	cfg = Config(size=6, win_length=4, max_timelines=3, allow_branch=True,
		cross_win_length=4, cross_win_mode="union")
	g = Game(cfg)
	for mv in [("place", 0, 0, 0), ("place", 0, 5, 5), ("branch", 0, 1, 1),
		("place", 0, 5, 4), ("place", 0, 3, 3), ("place", 0, 4, 4)]:
		(g.place if mv[0] == "place" else g.branch)(mv[1], mv[2], mv[3])
	assert not g.over  # not yet won after the seeded position
	g.branch(0, 2, 2)  # A forks t0 at (2,2) -> completes diagonal of 4 across timelines
	assert g.over and g.winner is A
	assert len({c[2] for c in g.winning_line.cells}) > 1  # genuinely cross-timeline
