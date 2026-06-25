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
	moves = _ordered_moves(game)
	if not moves:
		return None

	best, best_val = None, float("-inf")
	alpha = float("-inf")
	scored: list[tuple[float, Move]] = []
	for mv in moves:
		# Easy plays shallowly (near-best, not deep best), so search the easy candidates at
		# depth 0; everyone else uses the configured depth.
		val = _minimax(_apply(game, mv), 0 if difficulty == "easy" else depth - 1, alpha, float("inf"), me)
		scored.append((val, mv))
		if val > best_val:
			best_val, best = val, mv
		alpha = max(alpha, val)

	if difficulty == "easy":
		# Easy should be beatable by a flailing beginner: over half the time play a
		# genuinely random legal move (a real blunder), otherwise a near-best move.
		if random.random() < 0.55:
			return random.choice(legal_moves(game))
		good = [mv for val, mv in scored if val >= best_val - 1]
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


def _ordered_moves(game: Game) -> list[Move]:
	moves = legal_moves(game)
	# Cheap positional ordering (no board copy / full eval): explore moves next to existing
	# stones first — that's where lines form. Just for alpha-beta move order + truncation;
	# the leaf evaluation still does the real scoring.
	moves.sort(key=lambda m: _move_priority(game, m), reverse=True)
	return moves[:_MAX_BRANCHING]


def _move_priority(game: Game, move: Move) -> int:
	_, l, x, y = move
	board = game.timelines[l]
	score = 0
	for dx in (-1, 0, 1):
		for dy in (-1, 0, 1):
			if (dx or dy) and (x + dx, y + dy) in board:
				score += 2  # adjacent to a stone in this timeline
	for nl in (l - 1, l + 1):  # same cell in a neighbouring timeline — keeps forks/cross lines in view
		if 0 <= nl < len(game.timelines) and (x, y) in game.timelines[nl]:
			score += 2
	if move[0] == "branch":
		score -= 1  # a fork costs a tempo; try plain placements first
	return score


def _minimax(game: Game, depth: int, alpha: float, beta: float, me: Player) -> float:
	if game.winner is not None:
		return WIN_SCORE if game.winner is me else -WIN_SCORE
	if depth == 0:
		return _evaluate(game, me)
	moves = _ordered_moves(game)
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
	mode = game.config.cross_win_mode
	count_tl = len(game.timelines)
	score = 0.0
	seen: set[tuple] = set()
	for l, board in enumerate(game.timelines):
		for (x, y), owner in board.items():
			if owner is not p:
				continue
			for dx, dy, dl in _DIRECTIONS:
				# union/distinct cross wins aren't lattice-steps; score those separately below
				# and only keep in-board (dl == 0) step windows here.
				if mode != "step" and dl != 0:
					continue
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
	if mode != "step":
		score += _cross_diag_score(game, p, size, cross, count_tl)
	return score


def _cross_diag_score(game: Game, p: Player, size: int, cross: int, count_tl: int) -> float:
	"""Reward progress toward a cross-timeline diagonal (union/distinct modes): count diagonal
	cells the player already holds in some timeline, skipping segments the opponent has sealed
	off in every timeline. A bonus once the filled cells already span ≥2 timelines."""
	score = 0.0
	for dx, dy in ((1, 1), (1, -1)):
		for sx in range(size):
			for sy in range(size):
				ex, ey = sx + dx * (cross - 1), sy + dy * (cross - 1)
				if not (0 <= ex < size and 0 <= ey < size):
					continue
				filled = 0
				blocked = False
				tls_used: set[int] = set()
				for k in range(cross):
					cx, cy = sx + dx * k, sy + dy * k
					present = [l for l in range(count_tl) if game.timelines[l].get((cx, cy)) is p]
					if present:
						filled += 1
						tls_used.update(present)
					elif not any((cx, cy) not in game.timelines[l] for l in range(count_tl)):
						blocked = True  # every timeline occupies this cell, none of them ours
						break
				if blocked or filled == 0:
					continue
				score += 10 ** filled * (filled / cross) * (1.3 if len(tls_used) >= 2 else 1.0)
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
