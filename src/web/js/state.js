// Shared client-side view state. One mutable object the modules read/write.
export const view = {
	ws: null,
	queueWs: null,
	code: null,
	mode: null, // "hotseat" | "online" | "ai"
	seat: null, // "A" | "B" | null
	game: null, // latest server game state
	branchMode: false,
	explain: false,
	hover: null, // { l, x, y }
	cursor: null, // { l, x, y } keyboard focus cell
	kbNav: false, // true only while navigating by keyboard (hides cursor for mouse users)
	intentional: false, // set when we close the socket on purpose
	inTutorial: false,
	tutorialTarget: null, // { l, x, y } cell highlighted during a tutorial puzzle
};

export function resetForConnect() {
	view.seat = null;
	view.game = null;
	view.branchMode = false;
	view.hover = null;
	view.intentional = false;
}

export function myTurn() {
	const g = view.game;
	if (!g || g.winner) return false;
	return view.mode === "hotseat" || view.seat === g.current;
}

export function isEmptyCell(l, x, y) {
	return !view.game.timelines[l].some((s) => s.x === x && s.y === y);
}
