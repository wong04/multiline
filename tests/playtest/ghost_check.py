"""Verify the keyboard cursor (a faint preview orb) only shows during keyboard nav,
not after a mouse click — the 'ghost echo' bug."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H


def kbnav(page):
	return page.evaluate("() => window.__multiline.view.kbNav")


def main() -> int:
	pw, br, ctx, page = H.browser(headless=True)
	try:
		lob = H.Lobby(page)
		lob.goto()
		lob.pick_ruleset("full"); lob.pick_mode("ai"); lob.pick_difficulty("easy")
		lob.start()
		gv = H.GameView(page, H.Recorder("ghost", page))
		page.wait_for_timeout(800)
		# Mouse click a cell -> canvas focuses but keyboard cursor must stay hidden.
		gv.click_cell(0, 3, 3)
		page.wait_for_timeout(300)
		after_click = kbnav(page)
		# Now navigate by keyboard -> cursor should activate.
		page.focus("#board")
		page.keyboard.press("ArrowRight")
		page.wait_for_timeout(150)
		after_key = kbnav(page)
		# Move the mouse over a board cell -> keyboard cursor hidden again.
		pt = page.evaluate("() => window.__multiline.cellPoint(0, 5, 5)")
		page.mouse.move(pt["x"], pt["y"])
		page.wait_for_timeout(150)
		after_mouse = kbnav(page)
		print("RESULT ghost " + json.dumps({
			"kbNav_after_click": after_click,   # expect False (no ghost)
			"kbNav_after_arrow": after_key,     # expect True
			"kbNav_after_mousemove": after_mouse,  # expect False
			"fix_ok": after_click is False and after_key is True and after_mouse is False,
		}, ensure_ascii=False))
		return 0
	finally:
		ctx.close(); br.close(); pw.stop()


if __name__ == "__main__":
	raise SystemExit(main())
