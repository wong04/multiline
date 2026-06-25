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
DIFFICULTY = "normal"
GAMES_VS = 40           # per ruleset for the branch-aware vs place-only match
GAMES_SELFPLAY = 24     # per ruleset for self-play instrumentation
MAX_PLIES = 120


def _place_only_moves(game: Game):
	"""legal_moves restricted to placements — a player that can never fork."""
	return [m for m in ai.legal_moves(game) if m[0] == "place"]


def _choose(game: Game, allow_fork: bool):
	"""Pick a move like ai.choose_move, but optionally forbid branch moves."""
	if allow_fork:
		return ai.choose_move(game, DIFFICULTY)
	# Mirror choose_move's top-level selection over place-only candidates.
	depth = ai._DEPTH.get(DIFFICULTY, 2)
	me = game.current
	moves = [m for m in ai._ordered_moves(game, me) if m[0] == "place"]
	if not moves:
		moves = _place_only_moves(game)
	if not moves:
		return None
	best, best_val, alpha = None, float("-inf"), float("-inf")
	for mv in moves:
		val = ai._minimax(ai._apply(game, mv), depth - 1, alpha, float("inf"), me)
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
		move = _choose(game, allow)
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


def selfplay(cfg: Config, n: int) -> dict:
	"""Both sides branch-aware. Count branch usage and cross-timeline win share."""
	branch_moves = total_moves = wins = cross_wins = draws = plies = 0
	for _ in range(n):
		game = Game(cfg)
		p = 0
		for p in range(MAX_PLIES):
			if game.over:
				break
			move = ai.choose_move(game, DIFFICULTY)
			if move is None:
				break
			if move[0] == "branch":
				branch_moves += 1
			total_moves += 1
			_apply(game, move)
		plies += p
		if game.winner is None:
			draws += 1
		else:
			wins += 1
			if _cross_timeline(game):
				cross_wins += 1
	return {
		"games": n, "decisive": wins, "draws": draws,
		"branch_move_share": round(branch_moves / total_moves, 3) if total_moves else 0,
		"cross_timeline_win_share": round(cross_wins / wins, 3) if wins else 0,
		"avg_plies": round(plies / n, 1),
	}


def main() -> int:
	random.seed(1234)
	print(f"difficulty={DIFFICULTY}\n")
	for name, cfg in RULESETS.items():
		print(f"=== ruleset: {name} ({cfg.size}x{cfg.size}, win {cfg.win_length}, "
			f"≤{cfg.max_timelines} timelines) ===")
		m = match(cfg, GAMES_VS)
		print(f"  branch-aware vs place-only: {m}")
		s = selfplay(cfg, GAMES_SELFPLAY)
		print(f"  self-play:                  {s}")
		print()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
