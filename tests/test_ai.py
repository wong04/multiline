from src.engine.ai import choose_move
from src.engine.board import Config, Game
from src.engine.player import Player

A, B = Player.A, Player.B


def setup(stones, current=A, **cfg):
	config = Config(size=cfg.get("size", 5), win_length=cfg.get("win_length", 3),
		max_timelines=cfg.get("max_timelines", 1), allow_branch=cfg.get("allow_branch", False))
	g = Game(config)
	g.timelines[0] = dict(stones)
	g.current = current
	return g


def test_ai_takes_immediate_win():
	# A (to move) has two in a row; winning move completes three.
	g = setup({(0, 0): A, (1, 0): A, (0, 1): B, (1, 1): B}, current=A)
	assert choose_move(g, "normal") == ("place", 0, 2, 0)


def test_ai_blocks_immediate_loss():
	# B threatens to complete a row at (2,1); A (to move) must block there.
	g = setup({(0, 0): A, (0, 1): B, (1, 1): B}, current=A)
	assert choose_move(g, "normal") == ("place", 0, 2, 1)


def test_choose_move_none_when_over():
	g = setup({(0, 0): A, (1, 0): A, (2, 0): A}, current=B)
	g.winner = A
	assert choose_move(g, "normal") is None
