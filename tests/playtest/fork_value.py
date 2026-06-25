"""Phase 1: is forking actually worth it?

Engine-level experiment (no browser) to decide whether the "why fork?" confusion is a
teaching problem or a design problem. Reuses the real branch-aware AI.

Two measurements per ruleset:
  1. branch-aware AI vs place-only AI (same depth) — does the freedom to fork win games?
  2. self-play instrumentation — how often is branch chosen, and what share of wins are
     cross-timeline (a winning line spanning >1 timeline) vs in-board?

Run: uv run python tests/playtest/fork_value.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.engine import ai
from src.engine.board import Config, Game
from src.engine.player import Player

RULESETS = {
	"branch": Config(size=6, win_length=4, max_timelines=3, allow_branch=True, cross_win_length=3),
	"full": Config(size=8, win_length=5, max_timelines=4, allow_branch=True, cross_win_length=3),
}
SEARCH_DEPTH = 1  # set to 1 for a fast directional sweep, 2 to confirm a chosen config
GAMES_VS = 10           # per config for the branch-aware vs place-only match
GAMES_SELFPLAY = 8      # per config for self-play instrumentation
MAX_PLIES = 90


def best_move(game: Game, allow_fork: bool = True):
	"""Deterministic alpha-beta pick at SEARCH_DEPTH (no 'easy' randomness), optionally
	forbidding forks. Mirrors ai.choose_move's top-level selection."""
	me = game.current
	moves = ai._ordered_moves(game, me)
	if not allow_fork:
		moves = [m for m in moves if m[0] == "place"]
	if not moves:
		moves = [m for m in ai.legal_moves(game) if allow_fork or m[0] == "place"]
	if not moves:
		return None
	best, best_val, alpha = None, float("-inf"), float("-inf")
	for mv in moves:
		val = ai._minimax(ai._apply(game, mv), SEARCH_DEPTH - 1, alpha, float("inf"), me)
		if val > best_val:
			best_val, best = val, mv
		alpha = max(alpha, val)
	return best


def _apply(game: Game, move) -> None:
	if move[0] == "place":
		game.place(move[1], move[2], move[3])
	else:
		game.branch(move[1], move[2], move[3])


def _cross_timeline(game: Game) -> bool:
	if not game.winning_line:
		return False
	return len({c[2] for c in game.winning_line.cells}) > 1


def play(cfg: Config, a_forks: bool, b_forks: bool) -> tuple[Player | None, bool, int]:
	"""One game. Returns (winner, cross_timeline_win, plies)."""
	game = Game(cfg)
	for ply in range(MAX_PLIES):
		if game.over:
			break
		allow = a_forks if game.current is Player.A else b_forks
		move = best_move(game, allow)
		if move is None:
			break
		_apply(game, move)
	return game.winner, _cross_timeline(game), ply + 1


def match(cfg: Config, n: int) -> dict:
	"""branch-aware vs place-only, alternating who starts (seat A always moves first)."""
	aware_wins = restricted_wins = draws = cross = 0
	for i in range(n):
		# Alternate which side is branch-aware to cancel first-move advantage.
		aware_is_a = i % 2 == 0
		winner, ct, _ = play(cfg, a_forks=aware_is_a, b_forks=not aware_is_a)
		if winner is None:
			draws += 1
		elif (winner is Player.A) == aware_is_a:
			aware_wins += 1
			cross += ct
		else:
			restricted_wins += 1
	decided = aware_wins + restricted_wins
	return {
		"games": n, "branch_aware_wins": aware_wins, "place_only_wins": restricted_wins,
		"draws": draws,
		"branch_aware_winrate_decided": round(aware_wins / decided, 3) if decided else None,
		"cross_timeline_wins_by_aware": cross,
	}


def _median(xs: list[int]) -> float:
	s = sorted(xs)
	n = len(s)
	if not n:
		return 0
	return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def selfplay(cfg: Config, n: int) -> dict:
	"""Both sides branch-aware. Measures length, first-mover balance, depth proxies."""
	branch_moves = total_moves = wins = cross_wins = a_wins = draws = 0
	plies = []
	for _ in range(n):
		game = Game(cfg)
		p = 0
		for p in range(MAX_PLIES):
			if game.over:
				break
			move = best_move(game, True)
			if move is None:
				break
			if move[0] == "branch":
				branch_moves += 1
			total_moves += 1
			_apply(game, move)
		plies.append(p)
		if game.winner is None:
			draws += 1
		else:
			wins += 1
			a_wins += game.winner is Player.A
			cross_wins += _cross_timeline(game)
	return {
		"avg_plies": round(sum(plies) / n, 1),
		"median_plies": _median(plies),
		"first_mover_winrate": round(a_wins / wins, 2) if wins else None,
		"branch_move_share": round(branch_moves / total_moves, 2) if total_moves else 0,
		"cross_win_share": round(cross_wins / wins, 2) if wins else 0,
		"draws": draws,
	}


# Curated sweep for the "real game" board. Each entry: (size, win, cross, max_tl, keep_opp).
SWEEP = [
	(8, 5, 3, 4, False),   # OLD Full (asym baseline)
	(10, 5, 3, 4, True),   # NEW Full candidate: contestable, big board, discount 2
	(6, 4, 3, 3, True),    # NEW Branching (teaching) candidate: contestable
]


def main() -> int:
	print(f"search_depth={SEARCH_DEPTH}  (self-play n={GAMES_SELFPLAY}, match n={GAMES_VS})\n")
	hdr = f"{'size win/cross tl fork':24} {'avgPly':>6} {'medPly':>6} {'1stWR':>6} {'brMv':>5} {'xWin':>5} {'forkVal':>7}"
	print(hdr)
	print("-" * len(hdr))
	for size, win, cross, tl, keep in SWEEP:
		random.seed(1234)
		cfg = Config(size=size, win_length=win, max_timelines=tl,
			allow_branch=True, cross_win_length=cross, fork_keep_opponent=keep)
		s = selfplay(cfg, GAMES_SELFPLAY)
		m = match(cfg, GAMES_VS)
		label = f"{size}x{size} {win}/{cross} t{tl} {'sym' if keep else 'asym'}"
		print(f"{label:24} {s['avg_plies']:>6} {str(s['median_plies']):>6} "
			f"{str(s['first_mover_winrate']):>6} {str(s['branch_move_share']):>5} "
			f"{str(s['cross_win_share']):>5} {str(m['branch_aware_winrate_decided']):>7}")
	print("\nGoal: higher avgPly, 1stWR≈0.5, forkVal>0.6 but <1.0, xWin≈0.3-0.7.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
