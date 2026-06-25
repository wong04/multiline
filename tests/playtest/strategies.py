"""Move strategies for the three skill personas.

Each is `choose(state, gv) -> move | None` where move is
("place", l, x, y) or ("branch", source, x, y). State is the engine's to_dict()
shape: {timelines: [[{x,y,player,inherited}...]], config, current, winner, winningLine}.

These run client-side against the live server; the engine still validates every move.
"""

from __future__ import annotations

import random


def _occupied(state):
	occ = set()
	for l, tl in enumerate(state["timelines"]):
		for s in tl:
			occ.add((l, s["x"], s["y"]))
	return occ


def _empty_cells(state):
	size = state["config"]["size"]
	occ = _occupied(state)
	return [
		(l, x, y)
		for l in range(len(state["timelines"]))
		for x in range(size)
		for y in range(size)
		if (l, x, y) not in occ
	]


def _owner_grid(state, l):
	g = {}
	for s in state["timelines"][l]:
		g[(s["x"], s["y"])] = s["player"]
	return g


# In-board directions only (the harness keeps tactics simple — cross-timeline wins
# are explored by the expert via branching, not enumerated here).
_DIRS = ((1, 0), (0, 1), (1, 1), (1, -1))


def _line_len(grid, x, y, dx, dy, player, size):
	"""Length of contiguous `player` run through (x,y) in direction +/-(dx,dy)."""
	n = 1
	for sign in (1, -1):
		cx, cy = x + sign * dx, y + sign * dy
		while 0 <= cx < size and 0 <= cy < size and grid.get((cx, cy)) == player:
			n += 1
			cx += sign * dx
			cy += sign * dy
	return n


def _best_cell_for(state, player):
	"""Greedy: the empty in-board cell that makes `player`'s longest line."""
	size = state["config"]["size"]
	best, best_len = None, 0
	for l in range(len(state["timelines"])):
		grid = _owner_grid(state, l)
		occ = set(grid)
		for x in range(size):
			for y in range(size):
				if (x, y) in occ:
					continue
				longest = max(_line_len({**grid, (x, y): player}, x, y, dx, dy, player, size) for dx, dy in _DIRS)
				if longest > best_len:
					best_len, best = longest, (l, x, y)
	return best, best_len


# ---------------------------------------------------------------------------
def beginner(state, gv=None):
	"""Confused newcomer: a random legal placement; never branches."""
	cells = _empty_cells(state)
	if not cells:
		return None
	l, x, y = random.choice(cells)
	return ("place", l, x, y)


def intermediate(state, gv=None):
	"""Greedy: win if possible, else block the opponent, else extend own best line."""
	me = state["current"]
	other = "B" if me == "A" else "A"
	win = state["config"]["winLength"]

	mine, mine_len = _best_cell_for(state, me)
	if mine and mine_len >= win:
		return ("place", *mine)

	theirs, theirs_len = _best_cell_for(state, other)
	if theirs and theirs_len >= win - 1:
		return ("place", *theirs)  # block the threat

	if mine:
		return ("place", *mine)
	return beginner(state)


def expert(state, gv=None):
	"""Strongest of the three: greedy core + opportunistic branching to fork threats.

	If branching is allowed and we have a 2-in-a-row we could duplicate into a second
	timeline (the cross-timeline 'time-travel' pressure), occasionally do so; otherwise
	play the greedy intermediate move.
	"""
	cfg = state["config"]
	me = state["current"]
	win = cfg["winLength"]

	mine, mine_len = _best_cell_for(state, me)
	if mine and mine_len >= win:
		return ("place", *mine)

	other = "B" if me == "A" else "A"
	theirs, theirs_len = _best_cell_for(state, other)
	if theirs and theirs_len >= win - 1:
		return ("place", *theirs)

	can_branch = cfg.get("allowBranch") and len(state["timelines"]) < cfg["maxTimelines"]
	if can_branch and mine and mine_len >= max(2, win - 2) and random.random() < 0.5:
		# Fork the timeline where our line is strongest, extending it in the new copy.
		l, x, y = mine
		return ("branch", l, x, y)

	if mine:
		return ("place", *mine)
	return beginner(state)


STRATEGIES = {"beginner": beginner, "intermediate": intermediate, "expert": expert}
