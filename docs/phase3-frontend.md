# Phase 3 — Frontend: "Cosmic Playground"

## Direction
A bright, cartoon, sticker-book cosmos — joyful and effect-packed (inspired by 12wave.com),
**not** the earlier refined "Brass Instrument" (rejected for feeling like a centered landing
card). The cosmos is the subject, rendered playfully. Microcopy is kept **plain and game-y**
("Start Game", "Player A wins!") — lean into the visuals, keep the words simple.

- **Pieces:** bouncy glossy planet-orbs (squash/pop, no faces).
- **Mood:** bright vibrant sky (teal→blue→pink), sticker styling (thick outlines, offset
  shadows, big radii), boards are deep-space "windows" so orbs pop.
- **Type:** `Baloo 2` (chunky display) + `Fredoka` (UI/body).
- **Full-bleed scene:** gradient sky, floating planets with drift + mouse parallax, tilted
  wordmark, playful blob cursor, bouncy rocket loader — no centered "card" feel.

## Effects
Springy/overshoot motion everywhere; orb **place-pop + sparkles**; **elastic branch** (new
board boings in with a stretchy thread); **confetti + bouncy win line** on victory; chunky
buttons squash on press; `prefers-reduced-motion` calms it all.

## Files (`src/web/`)
- `index.html` — full-bleed scene shell (planets, sticker lobby, loader, cursor); preserves
  all element IDs the JS queries.
- `styles/tokens.css` (palette + fonts), `chrome.css` (sky, planets, cursor, loader),
  `app.css` (sticker layout, pill buttons, HUD, confetti, springy keyframes).
- `js/render.js` — glossy-orb stones, space-window boards, place-pop, elastic branch, bouncy
  win line. `js/main.js` — blob cursor, parallax, newly-placed pop diff, confetti.
  `js/ui.js` — plain status copy. `state.js`/`net.js`/`tutorial.js` unchanged in behaviour.

## Functional scope (unchanged from approved Phase 3)
3-lesson interactive tutorial; modes Hotseat / Online code / vs Computer (+difficulty) /
Quick-match; legend + tooltips + explain toggle; review #9 fixes. No engine/server changes.

## Verify
Run `uv run uvicorn src.server.app:app --reload`, open http://localhost:8000. Check the
bright scene + drifting planets + blob cursor; place-pop, branch boing, win confetti; all
modes + tutorial; `prefers-reduced-motion`. `node --check` JS; `uv run pytest` (35) stays
green. Re-deploy with `railway up`.
