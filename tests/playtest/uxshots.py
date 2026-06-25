"""Capture UX/accessibility evidence from the live site: screenshots at desktop &
mobile viewports, with and without reduced-motion, plus DOM probes (focus order,
aria/labels, modal escape). Writes to artifacts/ux/.

Usage: uv run python tests/playtest/uxshots.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H


def probe_focus_order(page) -> list[str]:
	"""Tab through the lobby and record what gets focus (id/tag)."""
	order = []
	page.evaluate("() => document.body.focus()")
	for _ in range(14):
		page.keyboard.press("Tab")
		el = page.evaluate(
			"() => { const a=document.activeElement; return a ? (a.id || a.tagName.toLowerCase()+(a.textContent?(':'+a.textContent.trim().slice(0,16)):'')) : null; }"
		)
		order.append(el)
	return order


def main() -> int:
	assert H.healthcheck(), "live unhealthy"
	report = {}

	# Desktop, normal motion.
	pw, br, ctx, page = H.browser(headless=True)
	try:
		rec = H.Recorder("ux", page)
		lob = H.Lobby(page)
		lob.goto()
		rec.shot("lobby-desktop")
		report["focus_order_desktop"] = probe_focus_order(page)
		report["cursor_none"] = page.evaluate(
			"() => getComputedStyle(document.body).cursor"
		)
		# Rulebook open/escape.
		lob.rulebook()
		page.wait_for_timeout(500)
		rec.shot("rulebook-open")
		report["rulebook_visible"] = page.is_visible("#rulebook:not(.hidden)")
		page.keyboard.press("Escape")
		page.wait_for_timeout(300)
		report["rulebook_escape_closes"] = not page.is_visible("#rulebook:not(.hidden)")
		# Tutorial.
		lob.tutorial()
		page.wait_for_timeout(800)
		rec.shot("tutorial-step1")
		report["tutorial_opened"] = page.is_visible("#tutorial:not(.hidden)") or page.is_visible("#table:not(.hidden)")
		# Start an AI game for an in-play screenshot.
		page.goto(H.LIVE_URL, wait_until="networkidle")
		page.wait_for_timeout(1000)
		lob2 = H.Lobby(page)
		lob2.pick_mode("ai"); lob2.pick_difficulty("normal"); lob2.pick_ruleset("full")
		lob2.start()
		page.wait_for_timeout(1000)
		gv = H.GameView(page, rec)
		st = gv.state()
		if st:
			from strategies import beginner
			for _ in range(4):
				if not gv.my_turn(gv.state()):
					page.wait_for_timeout(400); continue
				mv = beginner(gv.state())
				gv.click_cell(mv[1], mv[2], mv[3]); page.wait_for_timeout(500)
		rec.shot("game-inplay-desktop")
		report["status_text_sample"] = gv.status()
	finally:
		ctx.close(); br.close(); pw.stop()

	# Mobile viewport.
	pw, br, ctx, page = H.browser(headless=True, mobile=True)
	try:
		rec = H.Recorder("ux", page)
		H.Lobby(page).goto()
		rec.shot("lobby-mobile")
		report["mobile_horizontal_scroll"] = page.evaluate(
			"() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
		)
	finally:
		ctx.close(); br.close(); pw.stop()

	# Reduced motion.
	pw, br, ctx, page = H.browser(headless=True, reduced_motion=True)
	try:
		rec = H.Recorder("ux", page)
		H.Lobby(page).goto()
		rec.shot("lobby-reduced-motion")
	finally:
		ctx.close(); br.close(); pw.stop()

	print("RESULT ux " + json.dumps(report, ensure_ascii=False))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
