"""Loose check: can a random-clicking beginner now beat 'easy' AI?

Engine-level (no browser), so it tests the LOCAL ai.py change before deploy.
Random beginner = seat A; easy AI = seat B. Reports A's win rate per ruleset.
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
from strategies import intermediate

RULESETS = {
	"classic": Config(size=15, win_length=5, max_timelines=1, allow_branch=False),
	"full": Config(size=8, win_length=4, max_timelines=4, allow_branch=True),
}
N = 40
MAX_PLIES = 200


def random_move(game: Game):
	return random.choice(ai.legal_moves(game))


def greedy_move(game: Game):
	"""A 'beginner who tries': build lines / block, via the greedy strategy."""
	return intermediate(game.to_dict())


def play(cfg: Config, a_mover, b_diff: str):
	"""seat A uses a_mover(game); seat B uses easy/normal AI at b_diff."""
	game = Game(cfg)
	for _ in range(MAX_PLIES):
		if game.over:
			break
		mv = a_mover(game) if game.current is Player.A else ai.choose_move(game, b_diff)
		if mv is None:
			break
		(game.place if mv[0] == "place" else game.branch)(mv[1], mv[2], mv[3])
	return game.winner


def measure(label: str, cfg: Config, a_mover, b_diff: str):
	a = b = d = 0
	for _ in range(N):
		w = play(cfg, a_mover, b_diff)
		a += w is Player.A
		b += w is Player.B
		d += w is None
	print(f"  {label:34} A wins={a:3}  B wins={b:3}  unfinished={d:3}  -> A winrate={a / N:.0%}")


def main() -> int:
	for name, cfg in RULESETS.items():
		print(f"=== {name} ({cfg.size}x{cfg.size}, win {cfg.win_length}) ===")
		random.seed(7); measure("random beginner  vs EASY", cfg, random_move, "easy")
		random.seed(7); measure("trying beginner (greedy) vs EASY", cfg, greedy_move, "easy")
		random.seed(7); measure("trying beginner (greedy) vs NORMAL", cfg, greedy_move, "normal")
		print()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
