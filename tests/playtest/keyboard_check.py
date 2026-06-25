"""Verify the board is playable by keyboard alone (P0 accessibility fix)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H


def main() -> int:
	pw, br, ctx, page = H.browser(headless=True)
	try:
		rec = H.Recorder("keyboard", page)
		lob = H.Lobby(page)
		lob.goto()
		lob.pick_ruleset("full"); lob.pick_mode("ai"); lob.pick_difficulty("easy")
		lob.start()
		gv = H.GameView(page, rec)
		page.wait_for_timeout(800)
		before = sum(len(t) for t in (gv.state() or {}).get("timelines", []))
		page.focus("#board")
		page.wait_for_timeout(200)
		live_after_focus = page.text_content("#board-live")
		# Move with arrows, then place with Enter — no mouse at all.
		for key in ("ArrowRight", "ArrowDown", "Enter"):
			page.keyboard.press(key)
			page.wait_for_timeout(150)
		page.wait_for_timeout(600)
		after = sum(len(t) for t in (gv.state() or {}).get("timelines", []))
		rec.shot("keyboard-move")
		print("RESULT keyboard " + __import__("json").dumps({
			"stones_before": before, "stones_after": after,
			"placed_by_keyboard": after > before,
			"live_region_announces": bool(live_after_focus and "Timeline" in live_after_focus),
			"live_sample": live_after_focus,
		}, ensure_ascii=False))
		return 0
	finally:
		ctx.close(); br.close(); pw.stop()


if __name__ == "__main__":
	raise SystemExit(main())
