# Multiline — Playtest Findings & Improvement Plan

_Date: 2026-06-25 · Target: live site `https://multiline-production.up.railway.app`_

## How this was tested
Five "player" personas drove a **real Chromium browser** against the live site via a
Playwright harness (`tests/playtest/`). Personas: **beginner** (random legal moves),
**intermediate** (greedy: win/block/extend), **expert** (greedy + opportunistic branching),
a **multiplayer** runner (two/three browser contexts for online/quick-match/reconnect/
spectator), and a **UX/accessibility** reviewer (screenshots at desktop + mobile +
reduced-motion, focus-order/aria probes, source read). Every run wrote screenshots + a
JSONL event log under `tests/playtest/artifacts/<persona>/`. A read-only `window.__multiline`
hook (state + cell coordinates) was added to the front end so bots can read the board and
click exact cells; it changes no game behavior.

### Coverage
AI easy/normal/hard × beginner/intermediate/expert × classic/branch/full; hotseat; online
(room code, 2 contexts); quick-match (×2); reconnect; spectator; 3-lesson tutorial; rulebook;
adversarial probes (out-of-turn, occupied-cell, early reset).

### Known measurement gap (harness, not the game)
On the **full** ruleset, once the AI **branches** (creating a 2×2 multi-board layout), the
harness's pixel-clicks — computed from `getBoundingClientRect` — can target cells scrolled
out of the `overflow:auto` board container, so some moves were silently dropped client-side
and a few AI/full games ended "unfinished." **This is a harness limitation, not a product
bug.** I verified in `src/engine/board.py:45-56` that `place()` accepts a move into *any*
existing timeline at any empty cell — there is **no** "branched/echo timeline is read-only"
rule (an earlier agent guess to the contrary was wrong). Net effect: balance numbers on
**normal/full** are incomplete; everything else is solid. (Fix noted in Appendix.)

---

## Per-mode verdict
| Area | Verdict | Notes |
|---|---|---|
| Tutorial (3 lessons) | ✅ Works | All lessons complete & auto-detect; returns to lobby. Copy mismatches (below). |
| Rulebook | ✅ Works | Clear standalone coverage; opens/escapes correctly. |
| vs AI (easy) | ⚠️ Too hard | Random beginner lost 7/7; easy wins in ~4 moves, indistinguishable from normal. |
| vs AI (normal/hard) | ✅ Strong, snappy | AI beat the greedy bot 5/5 completed games; max think-time 844 ms. |
| Hotseat | ✅ Works | Clean full games, 0 rejected moves. |
| Online (room code) | ✅ Works | Seats A/B enforced; both clients stay in sync on result. |
| Quick-match | ✅ Reliable | 2/2 paired into same room, opposite seats. |
| Spectator | ✅ Works | 3rd joiner correctly read-only (`seat=null`). |
| Reconnect | ❌ Broken | Reload strands player on lobby (seat orphaned). |
| Accessibility | ❌ Blocking | Board is mouse-only; no keyboard play, no aria. |
| Mobile | ⚠️ Risky | Lobby fine; in-play board + blob cursor untested/likely awkward on touch. |

---

## Prioritized findings

### P0 — Blockers
- **A11y-1: The board cannot be played without a mouse.** `<canvas id="board">` binds only
  `mousemove`/`mouseleave`/`click` (`src/web/js/main.js:122-150`); no `tabindex`, `keydown`,
  role, or label. It never appears in the keyboard tab order. A keyboard-only/switch user can
  set up a game but cannot make a single move.
  → Add arrow-key cell navigation + Enter to place, a visible focus cell, and `role`/
  `aria-label` on the canvas with a live text representation of board state.
- **A11y-2: Board is invisible to screen readers.** Bare `<canvas>` (`index.html:119`) — no
  name/role; AT announces nothing. (`#status` text is good but the board itself is opaque.)
  → Pair with A11y-1: expose an off-screen/aria grid mirror of stones + whose turn.

### P1 — Major
- **Onboarding-1: One game, three vocabularies.** Tutorial says **"stars"** and
  **"Chart timeline"** (`src/web/js/tutorial.js:9,16`), but the rest of the game says
  **"planets"** (`index.html:42,147`, `main.js:131,204`) and the toggle button is labeled
  **"Fork"** (`index.html:108`, `ui.js:123`). A learner is told to flip a "Chart timeline"
  control that doesn't exist by that name. → Standardize on **planets** + **Fork** everywhere.
- **Onboarding-2: Tutorial teaches 5-in-a-row, default game is 4.** Lesson 1 runs `classic`
  ("FIVE in a row", `tutorial.js:9`) but the lobby default ruleset is `full` = 4-in-a-row
  (`ui.js:7`, goal text `index.html`). The silent ruleset switch misleads new players.
  → Surface the ruleset/goal in the tutorial, or align the post-tutorial default.
- **Difficulty-1: "Easy" is not easy.** A random beginner lost **7/7**, every full-ruleset
  game ending after ~4 of its moves; easy and normal produced identical outcomes (evidence:
  `artifacts/ai-beginner/events.jsonl`). Easy is meant to let a flailing newcomer sometimes
  win. → Make easy genuinely soft: more random moves, occasionally skip a block, shallow only.
- **MP-1: Reconnect strands the player.** After a reload with the same token, the seat is
  preserved **server-side** (`rooms.py:42-43`, `token_stable=true`) but the client lands back
  on the **lobby** (`auto_rejoined_table=false`, `seat_after=null`; screenshots
  `artifacts/reconnect/01-before-reload.png` → `02-after-reload.png`). Root cause: the client
  persists only `multiline-token`, never the room code (`net.js:4-11`). Worst in quick-match,
  where the player has no code to re-enter — they're stuck and the opponent waits forever.
  → Persist the room code; on load, auto-reconnect to an unfinished room for that token.
- **MP-2: No opponent-desertion handling.** Consequence of MP-1: the remaining player sits on
  "Waiting…" with no abandonment notice or reclaim path. → Add a disconnect/timeout notice.
- **A11y-3: `cursor:none` is applied globally.** `tokens.css` hides the system cursor for the
  whole body, replaced by a 22px blob. Users who rely on OS cursor size/contrast or have
  tracking difficulty lose their pointer everywhere. (Good: reduced-motion restores it — but
  that's the wrong proxy.) → Keep the native cursor; make the blob additive or a setting; and
  disable the blob on `(pointer: coarse)`.
- **Mobile-1: In-play board on touch is unverified and likely awkward.** Lobby is clean
  (no page h-scroll, fields stack), but the canvas is fixed-size inside `overflow:auto`
  (`app.css`), and the blob/hover model is `pointermove`-driven (`main.js:158`) so touch gets
  no hover hints and taps are unvalidated. → Scale the canvas to container width; disable the
  blob on touch; confirm tap-to-place; add an in-play mobile screenshot to the harness.

### P2 — Minor
- **UX-1: Clicking an occupied cell gives no feedback.** The client silently drops it
  (`main.js:139` returns when `!isEmptyCell`) — no hint/animation. The most common beginner
  mistake gets zero signal. → Show a brief "that cell's taken" hint, like the existing
  "Not your turn yet!".
- **UX-2: Silent move rejections.** Some rejected clicks surfaced an empty hint
  (`artifacts/ai-beginner/events.jsonl`). → Ensure every rejection states a reason.
- **A11y-4: Weak/again focus styles & modal focus management.** Controls style `:hover`/
  `:active` but lack `:focus-visible` rings; the rulebook dialog doesn't trap focus, move
  focus in on open, or restore it on close, and its Escape listener is always-on
  (`ui.js:77`). → Add `:focus-visible` outlines and standard dialog focus handling.
- **Contrast-1: Borderline small text.** Field-notes `--ink-soft #41507e` (~4.3:1) and the
  dim "Timeline N" label on the deep navy board are near the AA floor. → Darken/enlarge.
- **UX-3: Empty board reads as "broken/loading."** Before first render the board is a flat
  dark rectangle, sometimes still showing "Connecting…" next to the tutorial card
  (`artifacts/tutorial/`, `ux/` shots). → Draw an empty board frame/placeholder immediately.

### P3 — Nits
- Decorative emoji in buttons are read aloud ("robot Computer") — wrap glyphs in
  `aria-hidden` spans.
- "Now you're playing 5-dimensionally" (`tutorial.js:25`) is cute but unexplained.
- Tutorial card (`position:fixed` bottom) can overlap the lower board rows on short screens.
- `--win #ffe24a` and `--sun #ffd23f` are near-identical yellows (colorblind clarity).

---

## What works well (keep it)
- Quick-match pairing is reliable and reproducible; online room-code sync is clean; spectator
  enforcement and seat assignment are correct.
- Server-side robustness is solid: out-of-turn moves and pre-game-over resets are rejected
  with clear messages; the engine validated every move (hotseat: 0 rejects over a full game).
- AI is genuinely strong at normal/hard and **fast** (sub-second think time even at 3-ply),
  and it understands branching (the search explores branch moves).
- `prefers-reduced-motion` is fully respected (motion + custom cursor disabled).
- The "Cosmic Playground" lobby achieves its "no centered card" intent; mobile lobby stacks
  cleanly. Tutorial lessons are well-built (real hotseat rooms, auto-celebrate, skip-ahead).

---

## Recommended sequencing
1. **Accessibility pass (P0 + A11y-3/4):** keyboard board play + aria board mirror; stop
   hiding the system cursor; add focus-visible + dialog focus handling. _Biggest correctness
   gap; also unblocks mobile/touch thinking._
2. **Onboarding & difficulty (Onboarding-1/2, Difficulty-1):** unify vocabulary
   (planets/Fork), align tutorial↔default ruleset, make "easy" actually beatable. _Cheap,
   high impact on first-run retention._
3. **Reconnection (MP-1/2):** persist room code + auto-rejoin; add desertion notice. _Removes
   the only "broken" multiplayer path._
4. **Mobile/touch (Mobile-1):** responsive canvas + touch input + no blob on coarse pointers.
5. **Feedback polish (UX-1/2/3, Contrast-1):** occupied-cell + rejection hints, board
   placeholder, contrast bumps.
6. **Nits (P3)** as time allows.

---

## Appendix — re-enabling full-ruleset balance measurement
To get clean normal-vs-hard balance data on `full`, fix the harness (not the game): in
`tests/playtest/harness.py`, scroll the target cell into view before clicking (or `page.
mouse` after `scrollIntoViewIfNeeded` on the canvas region), and in
`tests/playtest/strategies.py` prefer the origin timeline / verify the chosen cell is empty
in the client's rendered state before returning it. Then re-run the `ai --ruleset full`
scenarios. The engine itself needs no change for this.
