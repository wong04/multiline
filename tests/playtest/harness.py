"""Playwright harness for play-testing the live Multiline site as a real browser.

The board is a <canvas>, so we read game state through the `window.__multiline` hook
(view + cellPoint) and click cells at their real pixel centres. All chrome is DOM.

Dev-only tooling — not shipped with the app. Requires:
    uv add --dev playwright && uv run playwright install chromium
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

import os

LIVE_URL = os.environ.get("MULTILINE_URL", "https://multiline-production.up.railway.app")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"

RULESETS = ("classic", "branch", "full")
MODES = ("ai", "hotseat", "online")
DIFFICULTIES = ("easy", "normal", "hard")


@dataclass
class Recorder:
	"""Per-persona evidence: a JSONL event log + numbered screenshots."""

	persona: str
	page: Page
	_dir: Path = field(init=False)
	_log: Path = field(init=False)
	_shot: int = field(default=0, init=False)

	def __post_init__(self) -> None:
		self._dir = ARTIFACTS / self.persona
		self._dir.mkdir(parents=True, exist_ok=True)
		self._log = self._dir / "events.jsonl"

	def log(self, event: str, **data) -> None:
		row = {"t": datetime.now(timezone.utc).isoformat(), "event": event, **data}
		with self._log.open("a", encoding="utf-8") as fh:
			fh.write(json.dumps(row) + "\n")

	def shot(self, label: str, page: Page | None = None) -> str:
		self._shot += 1
		name = f"{self._shot:02d}-{label}.png"
		(page or self.page).screenshot(path=str(self._dir / name), full_page=True)
		self.log("screenshot", file=name, label=label)
		return name


class Lobby:
	"""DOM page-object for the lobby controls (all real HTML elements)."""

	def __init__(self, page: Page):
		self.page = page

	def goto(self) -> None:
		self.page.goto(LIVE_URL, wait_until="networkidle")
		# Let the cosmetic loader clear.
		self.page.wait_for_timeout(1200)

	def pick_ruleset(self, ruleset: str) -> None:
		self.page.click("#ruleset-trigger")
		self.page.click(f'#ruleset-list li[data-value="{ruleset}"]')

	def pick_mode(self, mode: str) -> None:
		self.page.click(f'#mode button[data-mode="{mode}"]')

	def pick_difficulty(self, difficulty: str) -> None:
		self.page.click(f'#difficulty button[data-diff="{difficulty}"]')

	def start(self) -> None:
		self.page.click("#begin")
		self.page.wait_for_selector("#table:not(.hidden)", timeout=15000)

	def quickmatch(self) -> None:
		self.page.click("#quickmatch")

	def join(self, code: str) -> None:
		self.page.fill("#join-code", code)
		self.page.click("#join")
		self.page.wait_for_selector("#table:not(.hidden)", timeout=15000)

	def tutorial(self) -> None:
		self.page.click("#tutorial-start")

	def rulebook(self) -> None:
		self.page.click("#rulebook-open")


class GameView:
	"""In-game interactions: read state via the hook, click cells, read DOM status."""

	def __init__(self, page: Page, rec: Recorder):
		self.page = page
		self.rec = rec

	# ---- state ----
	def state(self) -> dict | None:
		return self.page.evaluate("() => window.__multiline ? window.__multiline.view.game : null")

	def seat(self) -> str | None:
		return self.page.evaluate("() => window.__multiline ? window.__multiline.view.seat : null")

	def mode(self) -> str | None:
		return self.page.evaluate("() => window.__multiline ? window.__multiline.view.mode : null")

	def status(self) -> str:
		return (self.page.text_content("#status") or "").strip()

	def hint(self) -> str:
		return (self.page.text_content("#hint") or "").strip()

	# ---- helpers ----
	def occupied(self, state: dict) -> set[tuple[int, int, int]]:
		cells = set()
		for l, tl in enumerate(state["timelines"]):
			for s in tl:
				cells.add((l, s["x"], s["y"]))
		return cells

	def empty_cells(self, state: dict) -> list[tuple[int, int, int]]:
		size = state["config"]["size"]
		occ = self.occupied(state)
		out = []
		for l in range(len(state["timelines"])):
			for x in range(size):
				for y in range(size):
					if (l, x, y) not in occ:
						out.append((l, x, y))
		return out

	def my_turn(self, state: dict) -> bool:
		mode = self.mode()
		if state.get("winner"):
			return False
		if mode == "hotseat":
			return True
		return self.seat() == state["current"]

	def set_branch(self, on: bool) -> None:
		txt = (self.page.text_content("#branch-toggle") or "").lower()
		is_on = "on" in txt
		if on != is_on and self.page.is_visible("#branch-toggle"):
			self.page.click("#branch-toggle")

	def click_cell(self, l: int, x: int, y: int) -> bool:
		pt = self.page.evaluate(
			"([l,x,y]) => window.__multiline.cellPoint(l,x,y)", [l, x, y]
		)
		if not pt:
			return False
		self.page.mouse.click(pt["x"], pt["y"])
		return True

	def reset(self) -> None:
		if self.page.is_visible("#reset"):
			self.page.click("#reset")

	def leave(self) -> None:
		if self.page.is_visible("#leave"):
			self.page.click("#leave")


def _progress(state: dict | None) -> tuple[int, int]:
	"""A signature that strictly increases as the game advances: (stones, timelines)."""
	if not state:
		return (0, 0)
	stones = sum(len(t) for t in state["timelines"])
	return (stones, len(state["timelines"]))


def _wait_for_change(gv: GameView, before: tuple[int, int], timeout_ms: int = 3000) -> bool:
	start = time.monotonic()
	while (time.monotonic() - start) * 1000 < timeout_ms:
		if _progress(gv.state()) != before:
			return True
		gv.page.wait_for_timeout(80)
	return False


def _wait_for_turn(gv: GameView, timeout_ms: int = 12000) -> tuple[dict | None, float]:
	"""Poll until it's our turn or the game ends. Returns (state, elapsed_ms)."""
	start = time.monotonic()
	while (time.monotonic() - start) * 1000 < timeout_ms:
		state = gv.state()
		if state is None:
			gv.page.wait_for_timeout(150)
			continue
		if state.get("winner") or gv.my_turn(state):
			return state, (time.monotonic() - start) * 1000
		gv.page.wait_for_timeout(120)
	return gv.state(), (time.monotonic() - start) * 1000


def play_game(gv: GameView, choose, max_moves: int = 80) -> dict:
	"""Drive one game to completion using `choose(state, gv) -> move | None`.

	move is ("place", l, x, y) or ("branch", source, x, y). Returns a summary dict
	including opponent/AI think-time latencies (ms).
	"""
	moves, rejected, latencies = 0, 0, []
	while moves < max_moves:
		state, waited = _wait_for_turn(gv)
		if waited > 50:
			latencies.append(round(waited))
		if state is None:
			gv.rec.log("no_state")
			break
		if state.get("winner"):
			break
		if not gv.my_turn(state):
			gv.rec.log("turn_timeout", status=gv.status())
			break

		move = choose(state, gv)
		if move is None:
			gv.rec.log("no_move_available")
			break
		gv.set_branch(move[0] == "branch")
		before = _progress(state)
		ok = gv.click_cell(move[1], move[2], move[3])
		if not ok:
			gv.rec.log("cell_point_missing", move=move)
			rejected += 1
			break
		if _wait_for_change(gv, before):
			moves += 1
		else:
			rejected += 1
			gv.rec.log("move_rejected", move=move, hint=gv.hint())
			if rejected > 6:  # persistent rejection — bail rather than spin
				break

	final = gv.state() or {}
	lat = latencies or [0]
	summary = {
		"moves": moves,
		"rejected": rejected,
		"winner": final.get("winner"),
		"timelines": len(final.get("timelines", [])),
		"status": gv.status(),
		"opp_latency_ms": {"max": max(lat), "avg": round(sum(lat) / len(lat))},
	}
	gv.rec.log("game_over", **summary)
	return summary


def browser(headless: bool = True, reduced_motion: bool = False, mobile: bool = False):
	"""Context manager-ish factory; returns (playwright, browser, context, page)."""
	pw = sync_playwright().start()
	br = pw.chromium.launch(headless=headless)
	kwargs = {}
	if reduced_motion:
		kwargs["reduced_motion"] = "reduce"
	if mobile:
		kwargs["viewport"] = {"width": 390, "height": 844}
		kwargs["is_mobile"] = True
		kwargs["has_touch"] = True
	ctx = br.new_context(**kwargs)
	page = ctx.new_page()
	return pw, br, ctx, page


def healthcheck() -> bool:
	import urllib.request

	with urllib.request.urlopen(f"{LIVE_URL}/healthz", timeout=10) as r:
		return json.loads(r.read())["status"] == "ok"
