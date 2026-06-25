"""Verify the board fits a phone-width screen without overflowing its container."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H


def main() -> int:
	pw, br, ctx, page = H.browser(headless=True, mobile=True)  # 390px wide
	try:
		rec = H.Recorder("mobile", page)
		lob = H.Lobby(page)
		lob.goto()
		lob.pick_ruleset("full"); lob.pick_mode("ai")
		lob.start()
		page.wait_for_timeout(900)
		rec.shot("mobile-inplay")
		dims = page.evaluate("""() => {
			const c = document.getElementById('board');
			const w = document.querySelector('.table-wrap');
			return { canvas: c.clientWidth, wrap: w.clientWidth,
				pageScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2 };
		}""")
		dims["canvas_fits_wrap"] = dims["canvas"] <= dims["wrap"]
		print("RESULT mobile " + json.dumps(dims, ensure_ascii=False))
		return 0
	finally:
		ctx.close(); br.close(); pw.stop()


if __name__ == "__main__":
	raise SystemExit(main())
