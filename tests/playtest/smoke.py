"""Smoke test: one full beginner-vs-AI game on the live site, to validate the harness."""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H
from strategies import beginner


def main() -> int:
	assert H.healthcheck(), "live site unhealthy"
	pw, br, ctx, page = H.browser(headless=True)
	try:
		rec = H.Recorder("smoke", page)
		lobby = H.Lobby(page)
		lobby.goto()
		rec.shot("lobby")
		lobby.pick_ruleset("full")
		lobby.pick_mode("ai")
		lobby.pick_difficulty("normal")
		lobby.start()
		rec.shot("game-start")
		gv = H.GameView(page, rec)
		page.wait_for_timeout(1000)
		print("seat=", gv.seat(), "mode=", gv.mode(), "current=", (gv.state() or {}).get("current"))
		summary = H.play_game(gv, beginner, max_moves=60)
		rec.shot("game-end")
		print("SUMMARY:", summary)
		return 0
	finally:
		ctx.close()
		br.close()
		pw.stop()


if __name__ == "__main__":
	raise SystemExit(main())
