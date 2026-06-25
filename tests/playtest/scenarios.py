"""Runnable play-test scenarios. Each writes screenshots + a JSONL log under
tests/playtest/artifacts/<persona>/ and prints a JSON summary to stdout.

Usage (PowerShell, with uv on PATH):
    uv run python tests/playtest/scenarios.py ai --persona beginner --diff easy --ruleset full --games 2
    uv run python tests/playtest/scenarios.py hotseat --ruleset branch
    uv run python tests/playtest/scenarios.py online --ruleset full
    uv run python tests/playtest/scenarios.py quickmatch
    uv run python tests/playtest/scenarios.py reconnect --ruleset full
    uv run python tests/playtest/scenarios.py spectator --ruleset full
    uv run python tests/playtest/scenarios.py adversarial --ruleset full
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H
from strategies import STRATEGIES


def _out(tag: str, data: dict) -> None:
	print(f"RESULT {tag} " + json.dumps(data, ensure_ascii=False))


def scenario_ai(args) -> None:
	persona = STRATEGIES[args.persona]
	results = []
	pw, br, ctx, page = H.browser(headless=not args.headed)
	try:
		rec = H.Recorder(f"ai-{args.persona}", page)
		for g in range(args.games):
			lobby = H.Lobby(page)
			lobby.goto()
			lobby.pick_ruleset(args.ruleset)
			lobby.pick_mode("ai")
			lobby.pick_difficulty(args.diff)
			lobby.start()
			gv = H.GameView(page, rec)
			if g == 0:
				rec.shot(f"{args.diff}-{args.ruleset}-start")
			summary = H.play_game(gv, persona)
			summary.update(diff=args.diff, ruleset=args.ruleset, game=g)
			results.append(summary)
			rec.log("ai_game", **summary)
			gv.leave()
		rec.shot(f"{args.diff}-{args.ruleset}-final")
	finally:
		ctx.close(); br.close(); pw.stop()
	human_wins = sum(1 for r in results if r["winner"] == "A")
	ai_wins = sum(1 for r in results if r["winner"] == "B")
	draws = sum(1 for r in results if not r["winner"])
	maxlat = max((r["opp_latency_ms"]["max"] for r in results), default=0)
	_out("ai", {
		"persona": args.persona, "diff": args.diff, "ruleset": args.ruleset,
		"games": len(results), "human_wins": human_wins, "ai_wins": ai_wins,
		"unfinished": draws, "max_ai_latency_ms": maxlat, "games_detail": results,
	})


def scenario_hotseat(args) -> None:
	pw, br, ctx, page = H.browser(headless=not args.headed)
	try:
		rec = H.Recorder("hotseat", page)
		lobby = H.Lobby(page)
		lobby.goto()
		lobby.pick_ruleset(args.ruleset)
		lobby.pick_mode("hotseat")
		lobby.start()
		gv = H.GameView(page, rec)
		rec.shot("hotseat-start")
		# In hotseat one client controls both sides; intermediate plays whoever is current.
		summary = H.play_game(gv, STRATEGIES["intermediate"])
		rec.shot("hotseat-end")
		_out("hotseat", {"ruleset": args.ruleset, **summary})
	finally:
		ctx.close(); br.close(); pw.stop()


def scenario_online(args) -> None:
	"""Two browser contexts: one creates an online room, the other joins by code."""
	pw, br, ctx_a, page_a = H.browser(headless=not args.headed)
	ctx_b = br.new_context()
	page_b = ctx_b.new_page()
	try:
		rec_a = H.Recorder("online-host", page_a)
		rec_b = H.Recorder("online-guest", page_b)
		lob_a = H.Lobby(page_a)
		lob_a.goto()
		lob_a.pick_ruleset(args.ruleset)
		lob_a.pick_mode("online")
		lob_a.start()
		gv_a = H.GameView(page_a, rec_a)
		page_a.wait_for_timeout(800)
		code = gv_a.page.evaluate("() => window.__multiline.view.code")
		rec_a.shot("host-room")
		lob_b = H.Lobby(page_b)
		lob_b.goto()
		lob_b.join(code)
		gv_b = H.GameView(page_b, rec_b)
		page_b.wait_for_timeout(800)
		rec_b.shot("guest-joined")
		seats = {"host": gv_a.seat(), "guest": gv_b.seat()}

		# Alternate: each context plays only when it's their turn.
		moves = 0
		import time as _t
		start = _t.monotonic()
		while moves < 60 and _t.monotonic() - start < 120:
			for gv in (gv_a, gv_b):
				st = gv.state()
				if st and st.get("winner"):
					moves = 999
					break
				if st and gv.my_turn(st):
					mv = STRATEGIES["intermediate"](st, gv)
					if mv:
						gv.set_branch(mv[0] == "branch")
						gv.click_cell(mv[1], mv[2], mv[3])
						gv.page.wait_for_timeout(250)
						moves += 1
			page_a.wait_for_timeout(150)
		rec_a.shot("host-final")
		rec_b.shot("guest-final")
		final = gv_a.state() or {}
		_out("online", {
			"ruleset": args.ruleset, "code": code, "seats": seats,
			"winner": final.get("winner"), "moves_played": min(moves, 60),
			"host_status": gv_a.status(), "guest_status": gv_b.status(),
		})
	finally:
		ctx_a.close(); ctx_b.close(); br.close(); pw.stop()


def scenario_quickmatch(args) -> None:
	"""Two contexts both hit quick-match; expect to be paired into one room."""
	pw, br, ctx_a, page_a = H.browser(headless=not args.headed)
	ctx_b = br.new_context()
	page_b = ctx_b.new_page()
	try:
		rec_a = H.Recorder("quickmatch-a", page_a)
		rec_b = H.Recorder("quickmatch-b", page_b)
		for lob in (H.Lobby(page_a), H.Lobby(page_b)):
			lob.goto()
		page_a.click("#quickmatch")
		page_a.wait_for_timeout(400)
		rec_a.shot("a-waiting")
		page_b.click("#quickmatch")
		# Wait for both to land in a table.
		paired = True
		try:
			page_a.wait_for_selector("#table:not(.hidden)", timeout=15000)
			page_b.wait_for_selector("#table:not(.hidden)", timeout=15000)
		except Exception:
			paired = False
		page_a.wait_for_timeout(800)
		gv_a, gv_b = H.GameView(page_a, rec_a), H.GameView(page_b, rec_b)
		code_a = page_a.evaluate("() => window.__multiline.view.code")
		code_b = page_b.evaluate("() => window.__multiline.view.code")
		rec_a.shot("a-matched"); rec_b.shot("b-matched")
		_out("quickmatch", {
			"paired": paired, "same_room": code_a == code_b,
			"code_a": code_a, "code_b": code_b,
			"seat_a": gv_a.seat(), "seat_b": gv_b.seat(),
		})
	finally:
		ctx_a.close(); ctx_b.close(); br.close(); pw.stop()


def scenario_reconnect(args) -> None:
	"""Play a few online moves, reload the host (same token), confirm seat+board survive."""
	pw, br, ctx_a, page_a = H.browser(headless=not args.headed)
	ctx_b = br.new_context()
	page_b = ctx_b.new_page()
	try:
		rec = H.Recorder("reconnect", page_a)
		lob_a = H.Lobby(page_a); lob_a.goto()
		lob_a.pick_ruleset(args.ruleset); lob_a.pick_mode("online"); lob_a.start()
		gv_a = H.GameView(page_a, rec)
		page_a.wait_for_timeout(800)
		code = page_a.evaluate("() => window.__multiline.view.code")
		token = page_a.evaluate("() => localStorage.getItem('multiline-token')")
		lob_b = H.Lobby(page_b); lob_b.goto(); lob_b.join(code)
		gv_b = H.GameView(page_b, rec)
		page_b.wait_for_timeout(600)
		# Host plays one move.
		st = gv_a.state()
		if st and gv_a.my_turn(st):
			mv = STRATEGIES["beginner"](st)
			gv_a.click_cell(mv[1], mv[2], mv[3])
			page_a.wait_for_timeout(400)
		before_seat = gv_a.seat()
		before_stones = sum(len(t) for t in (gv_a.state() or {}).get("timelines", []))
		rec.shot("before-reload")
		# Reload host (keeps localStorage token => same seat).
		page_a.reload(wait_until="networkidle")
		page_a.wait_for_timeout(1500)
		# It should auto be back in the table? The app reconnects only via UI; check state.
		after_token = page_a.evaluate("() => localStorage.getItem('multiline-token')")
		in_table = page_a.is_visible("#table:not(.hidden)")
		after_seat = gv_a.seat() if in_table else None
		after_stones = sum(len(t) for t in (gv_a.state() or {}).get("timelines", [])) if in_table else None
		rec.shot("after-reload")
		_out("reconnect", {
			"ruleset": args.ruleset, "token_stable": token == after_token,
			"auto_rejoined_table": in_table,
			"seat_before": before_seat, "seat_after": after_seat,
			"stones_before": before_stones, "stones_after": after_stones,
		})
	finally:
		ctx_a.close(); ctx_b.close(); br.close(); pw.stop()


def scenario_spectator(args) -> None:
	"""Third context joining a full online room should become a spectator."""
	pw, br, ctx_a, page_a = H.browser(headless=not args.headed)
	ctx_b = br.new_context(); page_b = ctx_b.new_page()
	ctx_c = br.new_context(); page_c = ctx_c.new_page()
	try:
		rec = H.Recorder("spectator", page_c)
		lob_a = H.Lobby(page_a); lob_a.goto()
		lob_a.pick_ruleset(args.ruleset); lob_a.pick_mode("online"); lob_a.start()
		page_a.wait_for_timeout(800)
		code = page_a.evaluate("() => window.__multiline.view.code")
		H.Lobby(page_b).goto(); H.Lobby(page_b).join(code)
		H.Lobby(page_c).goto(); H.Lobby(page_c).join(code)
		page_c.wait_for_timeout(800)
		gv_c = H.GameView(page_c, rec)
		rec.shot("spectator-view")
		_out("spectator", {
			"ruleset": args.ruleset, "code": code,
			"spectator_seat": gv_c.seat(), "spectator_status": gv_c.status(),
		})
	finally:
		ctx_a.close(); ctx_b.close(); ctx_c.close(); br.close(); pw.stop()


def scenario_adversarial(args) -> None:
	"""Abuse cases: out-of-turn click, occupied cell, reset gating in online."""
	findings = {}
	pw, br, ctx_a, page_a = H.browser(headless=not args.headed)
	ctx_b = br.new_context(); page_b = ctx_b.new_page()
	try:
		rec = H.Recorder("adversarial", page_a)
		lob_a = H.Lobby(page_a); lob_a.goto()
		lob_a.pick_ruleset(args.ruleset); lob_a.pick_mode("online"); lob_a.start()
		gv_a = H.GameView(page_a, rec)
		page_a.wait_for_timeout(800)
		code = page_a.evaluate("() => window.__multiline.view.code")
		lob_b = H.Lobby(page_b); lob_b.goto(); lob_b.join(code)
		gv_b = H.GameView(page_b, rec)
		page_b.wait_for_timeout(800)

		# Whoever is NOT current tries to move (out of turn).
		st = gv_a.state()
		mover, waiter = (gv_a, gv_b) if gv_a.my_turn(st) else (gv_b, gv_a)
		empty = waiter.empty_cells(st)[0]
		waiter.click_cell(*empty)
		page_a.wait_for_timeout(400)
		findings["out_of_turn_hint"] = waiter.hint()
		findings["out_of_turn_blocked"] = sum(len(t) for t in (gv_a.state() or {}).get("timelines", [])) == 0

		# Legit move, then opponent clicks the SAME (now occupied) cell.
		st = gv_a.state()
		mover = gv_a if gv_a.my_turn(st) else gv_b
		cell = mover.empty_cells(st)[0]
		mover.click_cell(*cell)
		page_a.wait_for_timeout(400)
		other = gv_b if mover is gv_a else gv_a
		st2 = other.state()
		if other.my_turn(st2):
			other.click_cell(*cell)  # occupied
			page_a.wait_for_timeout(400)
			findings["occupied_click_hint"] = other.hint()

		# Reset before game over in online should be rejected.
		gv_a.reset()
		page_a.wait_for_timeout(400)
		findings["early_reset_hint"] = gv_a.hint()
		findings["early_reset_blocked"] = (gv_a.state() or {}).get("current") is not None and \
			sum(len(t) for t in (gv_a.state() or {}).get("timelines", [])) > 0
		rec.shot("adversarial")
		_out("adversarial", {"ruleset": args.ruleset, **findings})
	finally:
		ctx_a.close(); ctx_b.close(); br.close(); pw.stop()


def scenario_tutorial(args) -> None:
	"""Walk the 3-lesson tutorial: solve lessons 1 & 2, capture copy, reach Finish."""
	pw, br, ctx, page = H.browser(headless=not args.headed)
	try:
		rec = H.Recorder("tutorial", page)
		H.Lobby(page).goto()
		page.click("#tutorial-start")
		page.wait_for_selector("#tutorial:not(.hidden)", timeout=15000)
		gv = H.GameView(page, rec)
		lessons = []

		def capture(i):
			page.wait_for_timeout(900)
			lessons.append({
				"step": page.text_content("#tutorial-step"),
				"title": page.text_content("#tutorial-title"),
				"body": (page.text_content("#tutorial-body") or "")[:160],
			})
			rec.shot(f"lesson{i}")

		# Lesson 1: classic 5-in-a-row. Give A a vertical line; dump B far away.
		capture(1)
		a_row, b_row = 0, 0
		for _ in range(40):
			st = gv.state()
			if not st or st.get("winner"):
				break
			cur = st["current"]
			before = H._progress(st)
			if cur == "A":
				gv.click_cell(0, 0, a_row); a_row += 1
			else:
				gv.click_cell(0, st["config"]["size"] - 1, b_row); b_row += 1
			H._wait_for_change(gv, before, 2500)
		l1_solved = "glow" in (page.get_attribute("#tutorial-next", "class") or "") or "✦" in gv.hint()
		rec.shot("lesson1-result")
		page.click("#tutorial-next", force=True)

		# Lesson 2: fork a timeline.
		capture(2)
		st = gv.state()
		before = H._progress(st)
		gv.set_branch(True)
		empty = gv.empty_cells(st)[0]
		gv.click_cell(*empty)
		H._wait_for_change(gv, before, 2500)
		l2_solved = len((gv.state() or {}).get("timelines", [])) > 1
		rec.shot("lesson2-result")
		page.click("#tutorial-next", force=True)

		# Lesson 3: capture only, then Finish.
		capture(3)
		page.click("#tutorial-next", force=True)  # "Finish"
		page.wait_for_timeout(800)
		back_to_lobby = page.is_visible("#console:not(.hidden)")
		rec.shot("after-finish")
		_out("tutorial", {
			"lessons": lessons, "lesson1_win_detected": l1_solved,
			"lesson2_fork_detected": l2_solved, "returned_to_lobby": back_to_lobby,
		})
	finally:
		ctx.close(); br.close(); pw.stop()


def main() -> int:
	p = argparse.ArgumentParser()
	sub = p.add_subparsers(dest="cmd", required=True)
	pa = sub.add_parser("ai"); pa.add_argument("--persona", default="beginner")
	pa.add_argument("--diff", default="normal"); pa.add_argument("--ruleset", default="full")
	pa.add_argument("--games", type=int, default=2)
	for name in ("hotseat", "online", "reconnect", "spectator", "adversarial"):
		sp = sub.add_parser(name); sp.add_argument("--ruleset", default="full")
	sub.add_parser("quickmatch")
	sub.add_parser("tutorial")
	for sp in sub.choices.values():
		sp.add_argument("--headed", action="store_true")

	args = p.parse_args()
	fn = {
		"ai": scenario_ai, "hotseat": scenario_hotseat, "online": scenario_online,
		"quickmatch": scenario_quickmatch, "reconnect": scenario_reconnect,
		"spectator": scenario_spectator, "adversarial": scenario_adversarial,
		"tutorial": scenario_tutorial,
	}[args.cmd]
	if not H.healthcheck():
		print("LIVE SITE UNHEALTHY", file=sys.stderr)
		return 2
	fn(args)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
