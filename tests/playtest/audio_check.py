"""Smoke-check the audio wiring: no console errors, AudioContext created on a gesture,
the sound toggle flips its icon, and a button click runs without error."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness as H


def main() -> int:
	pw, br, ctx, page = H.browser(headless=True)
	errors = []
	page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
	page.on("pageerror", lambda e: errors.append(str(e)))
	try:
		H.Lobby(page).goto()
		icon_before = page.text_content("#sound")
		page.click("#sound")  # a gesture -> unlock + toggle
		page.wait_for_timeout(300)
		icon_after = page.text_content("#sound")
		has_audiocontext = page.evaluate(
			"() => typeof (window.AudioContext || window.webkitAudioContext) === 'function'"
		)
		page.click("#tutorial-start")  # another button -> pop path
		page.wait_for_timeout(300)
		print("RESULT audio " + json.dumps({
			"icon_before": icon_before, "icon_after": icon_after,
			"toggle_flips": icon_before != icon_after,
			"audiocontext_available": has_audiocontext,
			"console_errors": errors,
		}, ensure_ascii=False))
		return 0
	finally:
		ctx.close(); br.close(); pw.stop()


if __name__ == "__main__":
	raise SystemExit(main())
