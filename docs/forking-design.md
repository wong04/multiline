# Making forking worth it — lessons from 5D Chess

_Why "why fork?" is confusing in Multiline, what 5D Chess does to make branching powerful,
and concrete ways to import that. Companion to the measured finding in
[playtest-findings.md](playtest-findings.md) (forking currently wins 50/50 — i.e. no edge)._

## What makes branching worth it in 5D Chess
From the game's design + community strategy writing:
1. **A branch opens a new front the opponent must defend.** You time-travel/branch to strike
   where they aren't prepared; the classic win is a **fork across timelines** — two threats
   they can't both answer.
2. **The defender must be safe *everywhere*; the attacker only needs one breakthrough.** Win =
   checkmate across all active timelines, so spreading the battle favors the aggressor.
3. **Pieces have *reach* across the new dimensions.** A piece acts through time/timelines, so
   creating boards multiplies your pieces' power (queens become ~3× as valuable).
4. **Branching is a scarce, contested resource.** Your timeline cap is tied to the opponent's;
   the ability to branch is "worth more than a queen," so you hoard it for the decisive moment.
5. **Tempo across boards.** Forcing responses on multiple timelines wins time.

Sources: [Wikipedia](https://en.wikipedia.org/wiki/5D_Chess_with_Multiverse_Time_Travel) ·
[High West Academy strategy](https://highwestacademy.com/blog/5d-chess-multiverse-time-travel) ·
[Steam: pieces through time & timelines](https://steamcommunity.com/sharedfiles/filedetails/?id=2176513845) ·
[TV Tropes](https://tvtropes.org/pmwiki/pmwiki.php/VideoGame/FiveDChessWithMultiverseTimeTravel)

## Why Multiline's fork is inert (diagnosis)
Mapping those principles against our mechanic ([board.py branch](src/engine/board.py#L58),
[win.py](src/engine/win.py)):
- **No new front (vs principle 1/2):** forking copies the **whole** board — *both* players'
  stones — so the new timeline is symmetric. You gain nothing the opponent doesn't also gain.
- **No reach (vs 3):** stones are inert after placement; the only cross-timeline interaction is
  one specific diagonal win-line. A stone doesn't threaten across boards.
- **The extra dimension is the *hard* path, not the rewarding one (vs 2):** an in-board win
  needs `win_length` in one board (fast); a cross-timeline win needs `win_length` stones across
  `win_length` boards built one-per-turn. So in-board always finishes first — our data: games
  end in ~5 plies, 0% cross-timeline, AI never forks.
- **Not a resource, no tempo (vs 4/5):** forking just costs a tempo for no compensating threat.

**Conclusion:** forking is weak *by design*, not just under-explained. To make "why fork?"
self-evident, the mechanic needs to import at least one of: **asymmetry**, **reach**, or
**objective tuning** so the extra dimension is the efficient/forced route to victory.

## Implementation options (for Multiline)

### Lever A — Make cross-timeline wins the *efficient* path (objective tuning) — simplest
Let a line that **spans timelines** need fewer stones than an in-board line. Add
`Config.cross_win_length` (default = `win_length`, so nothing changes unless a ruleset sets
it). In [win.py](src/engine/win.py), use `win_length` for `dl == 0` directions and
`cross_win_length` for `dl != 0`. Example: in-board needs 5, cross-timeline needs 3 → forking
becomes the fast win, so players *want* to fork.
- Pro: tiny, backward-compatible, fully measurable with `fork_value.py`. No new concepts.
- Con: doesn't add an attacking *front* by itself; it makes the dimension attractive, not
  asymmetric.

### Lever B — Asymmetric fork: the new timeline carries only YOUR planets — most faithful
When you fork, the copy keeps only the **forking player's** planets (opponent's are dropped),
plus your new placement. Now the fork is a board where **you're ahead** — a fresh front the
opponent must scramble to contest. Directly imports 5D's "branch to open an attack."
- Pro: creates real tempo / multi-front pressure; very teachable ("spin off a new board with
  just your planets — a head start your opponent has to chase").
- Con: bigger rule change in `branch()`; could be strong — balance via `max_timelines` and the
  shared timeline cap; echoes/legend copy update.

### Lever C — Stones project across timelines (reach) — most 5D-like, most complex
A planet also counts (for win-lines/threats) at its cell in adjacent timelines. Placements
become multi-purpose; forking multiplies reach.
- Pro: closest to 5D's cross-dimensional pieces.
- Con: large rules + rendering + balance change; changes the game's feel a lot.

### Lever D — Branching as a scarce resource (economy) — optional depth, complements A/B
Adopt 5D's cap rule (your timeline limit tied to opponent's branches) so branching is a hoarded
high-value action. Alone it doesn't make forking *win*; it adds "use it at the right moment"
depth. Probably more than a casual game needs — note for later.

## Result — A + B implemented & measured (2026-06-25)
Implemented both: `cross_win_length` (A) so cross-timeline lines need fewer stones, and an
**asymmetric fork** (B) — `branch()` now carries only the forking player's planets. Re-ran
`fork_value.py` (was 50/50 with 0% cross before):

| ruleset (in-board / cross) | branch-aware vs place-only | AI branch-move share | cross-timeline win share |
|---|---|---|---|
| branch — 6×6, 4 / 3 | 0.50 (20–20), **all aware wins cross** | 29% | balanced |
| full — 8×8, 5 / 3 | **1.00 (40–0)**, all cross | 43% | **100%** |

Forking went from **worthless → central**: the AI now forks ~30–43% of moves and wins across
timelines. **branch** stays balanced (forking co-equal — ideal for teaching); **full** is now
multiverse-centric (forking is the path), fitting "Full = the real game." Shipped rulesets:
branch `win 4 / cross 3 / ≤3 TL`, full `win 5 / cross 3 / ≤4 TL`.

## Update 2 — longer & deeper retune (2026-06-25)
Feedback: games felt **too short and shallow** (~5–7 plies). Measured cause: the asymmetric
fork made cross-wins an **uncontested race** — self-play ended in ~7 plies with **first-mover
winning 100%** and nothing to defend. Sweep findings (`fork_value.py`, depth 1–2):

| config | avg plies | first-mover WR | note |
|---|---|---|---|
| 8×8 5/3, **asymmetric** (old Full) | ~5–7 | **1.0** | short, unbalanced, uncontested |
| 10×10 5/3, **contestable** (new Full) | ~9 @depth1, **very long @depth2** | — | depth-2 self-play too long to finish in budget = deep, contested games |

So we **made forks contestable** (`fork_keep_opponent=True`, now the default): a fork copies
the *whole* board, so the opponent defends across timelines → real calculation and ~2×+ longer
games. The cross-length discount stays (cross 3 vs in-board 5) so forking remains a strong
*advanced* option rather than a shallow auto-win. Shipped: **Full/quick-match = 10×10, 5 / 3,
≤4 TL, contestable**; **Branching = 6×6, 4 / 3, ≤3 TL, contestable**.

Caveat: measuring forking's value for contestable configs needs deeper search than was
feasible to sweep here (a shallow bot under-uses forks); the choice rests on the length/balance
data plus the design reasoning above. Revisit with a deeper-bot run or live feedback if forking
feels under- or over-powered.

## Recommendation
Prototype **A first** (cheap, measurable): make cross-timeline the efficient win and re-run
`fork_value.py` — if forking starts winning and the AI starts branching, that may be enough.
If it still feels flat, add **B** (asymmetric fork) for a genuine attacking front. Then build
the guided fork-to-win tutorial + copy on a mechanic that actually rewards forking. Hold C/D
unless we want to go deeper.
