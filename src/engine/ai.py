"""A depth-limited alpha-beta opponent for Multiline.

Moves are tuples: ("place", timeline, x, y) or ("branch", source, x, y).
Candidate moves are pruned to cells near existing stones (line games only matter
next to play), and search is capped per node, so it stays fast on small boards.
"""

from __future__ import annotations

import random

from .board import Game
from .player import Player
from .win import _DIRECTIONS

Move = tuple

WIN_SCORE = 1_000_000
_MAX_BRANCHING = 14  # candidate moves explored per search node
_DEPTH = {"easy": 1, "normal": 2, "hard": 3}


def choose_move(game: Game, difficulty: str = "normal") -> Move | None:
	if game.over:
		return None
	depth = _DEPTH.get(difficulty, 2)
	me = game.current
	moves = _ordered_moves(game, me)
	if not moves:
		return None

	best, best_val = None, float("-inf")
	alpha = float("-inf")
	for mv in moves:
		val = _minimax(_apply(game, mv), depth - 1, alpha, float("inf"), me)
		if val > best_val:
			best_val, best = val, mv
		alpha = max(alpha, val)

	if difficulty == "easy":
		# Easy should be beatable by a flailing beginner: over half the time play a
		# genuinely random legal move (a real blunder), otherwise a near-best move.
		if random.random() < 0.55:
			return random.choice(legal_moves(game))
		good = [m for m in moves if _minimax(_apply(game, m), 0, float("-inf"), float("inf"), me) >= best_val - 1]
		return random.choice(good) if good else best
	return best


def legal_moves(game: Game) -> list[Move]:
	moves: list[Move] = []
	for l in range(len(game.timelines)):
		for (x, y) in _candidate_cells(game, l):
			moves.append(("place", l, x, y))
	if game.config.allow_branch and len(game.timelines) < game.config.max_timelines:
		for l in range(len(game.timelines)):
			for (x, y) in _candidate_cells(game, l):
				moves.append(("branch", l, x, y))
	if not moves:  # fallback: any empty cell anywhere
		size = game.config.size
		for l, board in enumerate(game.timelines):
			for x in range(size):
				for y in range(size):
					if (x, y) not in board:
						moves.append(("place", l, x, y))
	return moves


def _apply(game: Game, move: Move) -> Game:
	clone = game.copy()
	if move[0] == "place":
		clone.place(move[1], move[2], move[3])
	else:
		clone.branch(move[1], move[2], move[3])
	return clone


def _candidate_cells(game: Game, l: int) -> set[tuple[int, int]]:
	size = game.config.size
	board = game.timelines[l]
	if not board:
		return {(size // 2, size // 2)}
	cells: set[tuple[int, int]] = set()
	for (sx, sy) in board:
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				nx, ny = sx + dx, sy + dy
				if 0 <= nx < size and 0 <= ny < size and (nx, ny) not in board:
					cells.add((nx, ny))
	return cells


def _ordered_moves(game: Game, me: Player) -> list[Move]:
	moves = legal_moves(game)
	# Order by the static evaluation of the resulting position (best first).
	scored = sorted(
		moves, key=lambda m: _evaluate(_apply(game, m), me), reverse=True
	)
	return scored[:_MAX_BRANCHING]


def _minimax(game: Game, depth: int, alpha: float, beta: float, me: Player) -> float:
	if game.winner is not None:
		return WIN_SCORE if game.winner is me else -WIN_SCORE
	if depth == 0:
		return _evaluate(game, me)
	moves = _ordered_moves(game, game.current)
	if not moves:
		return _evaluate(game, me)

	if game.current is me:
		value = float("-inf")
		for mv in moves:
			value = max(value, _minimax(_apply(game, mv), depth - 1, alpha, beta, me))
			alpha = max(alpha, value)
			if alpha >= beta:
				break
		return value
	value = float("inf")
	for mv in moves:
		value = min(value, _minimax(_apply(game, mv), depth - 1, alpha, beta, me))
		beta = min(beta, value)
		if alpha >= beta:
			break
	return value


def _evaluate(game: Game, me: Player) -> float:
	if game.winner is me:
		return WIN_SCORE
	if game.winner is not None:
		return -WIN_SCORE
	return _player_score(game, me) - _player_score(game, me.other)


def _player_score(game: Game, p: Player) -> float:
	"""Sum over windows containing only `p` stones (and empties), weighted by count.

	Cross-timeline windows (dl != 0) use the shorter cross length, so a near-complete
	cross threat is scored relative to *its* shorter target — making forks attractive.
	"""
	size = game.config.size
	win_in = game.config.win_length
	cross = game.config.cross_len
	count_tl = len(game.timelines)
	score = 0.0
	seen: set[tuple] = set()
	for l, board in enumerate(game.timelines):
		for (x, y), owner in board.items():
			if owner is not p:
				continue
			for dx, dy, dl in _DIRECTIONS:
				target = win_in if dl == 0 else cross
				for off in range(target):
					sx, sy, sl = x - off * dx, y - off * dy, l - off * dl
					key = (sx, sy, sl, dx, dy, dl)
					if key in seen:
						continue
					seen.add(key)
					mine = _window_score(game, sx, sy, sl, dx, dy, dl, target, p, size, count_tl)
					if mine > 0:
						# Weight by closeness to this window's target (cross targets are shorter,
						# so a 2/3 cross threat outranks a 2/5 in-board one).
						score += 10 ** mine * (mine / target)
	return score


def _window_score(game, sx, sy, sl, dx, dy, dl, win, p, size, count_tl) -> int:
	"""Count of p-stones in the window, or -1 if out of bounds or blocked by opponent."""
	mine = 0
	for k in range(win):
		nx, ny, nl = sx + dx * k, sy + dy * k, sl + dl * k
		if not (0 <= nx < size and 0 <= ny < size and 0 <= nl < count_tl):
			return -1
		owner = game.timelines[nl].get((nx, ny))
		if owner is None:
			continue
		if owner is not p:
			return -1  # opponent stone blocks this window
		mine += 1
	return mine
