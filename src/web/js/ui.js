// DOM: lobby console, HUD status, pickers, toggles, tutorial overlay shell.
import { view } from "./state.js";

export const RULESETS = {
	classic: { size: 15, winLength: 5, maxTimelines: 1, allowBranch: false },
	branch: { size: 6, winLength: 3, maxTimelines: 3, allowBranch: true },
	full: { size: 8, winLength: 4, maxTimelines: 4, allowBranch: true },
};

const RULESET_NOTE = {
	classic: "Just make a line. No timelines — learn the base.",
	branch: "Small board, easy forks — pull off cross-timeline wins.",
	full: "The full multiverse: branch and win across timelines.",
};
const MODE_NOTE = {
	ai: "Play the computer — pick a difficulty.",
	hotseat: "Two players share this one device.",
	online: "Begin creates a room code to share; or Join one.",
};

const $ = (id) => document.getElementById(id);
let els = {};
let sel = { mode: "ai", ruleset: "full", difficulty: "normal" };
let hintTimer = null;

export function initUI(actions) {
	els = {
		console: $("console"), table: $("table"),
		ruleset: $("ruleset"), rulesetNote: $("ruleset-note"),
		mode: $("mode"), modeNote: $("mode-note"),
		difficultyField: $("difficulty-field"), difficulty: $("difficulty"),
		begin: $("begin"), quickmatch: $("quickmatch"),
		joinCode: $("join-code"), join: $("join"),
		status: $("status"), dot: document.querySelector(".readout-dot"),
		roomPill: $("room-pill"), hint: $("hint"),
		branchToggle: $("branch-toggle"), explainToggle: $("explain-toggle"),
		reset: $("reset"), leave: $("leave"), help: $("help"),
		goal: $("goal-text"), waiting: $("waiting-banner"), waitingCancel: $("waiting-cancel"),
		tutorialStart: $("tutorial-start"),
		rulebook: $("rulebook"), rulebookOpen: $("rulebook-open"),
		rulebookClose: $("rulebook-close"), rulesChip: $("rules-chip"),
	};

	els.ruleset.addEventListener("change", () => {
		sel.ruleset = els.ruleset.value;
		els.rulesetNote.textContent = RULESET_NOTE[sel.ruleset];
	});
	els.rulesetNote.textContent = RULESET_NOTE[sel.ruleset];
	els.modeNote.textContent = MODE_NOTE[sel.mode];

	bindSegmented(els.mode, "mode", (val) => {
		sel.mode = val;
		els.modeNote.textContent = MODE_NOTE[val];
		els.difficultyField.style.opacity = val === "ai" ? "1" : "0.35";
		els.difficultyField.style.pointerEvents = val === "ai" ? "auto" : "none";
	});
	bindSegmented(els.difficulty, "diff", (val) => { sel.difficulty = val; });

	els.begin.addEventListener("click", actions.begin);
	els.quickmatch.addEventListener("click", actions.quickmatch);
	els.join.addEventListener("click", actions.join);
	els.joinCode.addEventListener("keydown", (e) => { if (e.key === "Enter") actions.join(); });
	els.branchToggle.addEventListener("click", actions.branchToggle);
	els.explainToggle.addEventListener("click", actions.explainToggle);
	els.reset.addEventListener("click", actions.reset);
	els.leave.addEventListener("click", actions.leave);
	els.help.addEventListener("click", actions.help);
	els.tutorialStart.addEventListener("click", actions.help);
	els.waitingCancel.addEventListener("click", actions.cancelQueue);

	const openBook = () => els.rulebook.classList.remove("hidden");
	const closeBook = () => els.rulebook.classList.add("hidden");
	els.rulebookOpen.addEventListener("click", openBook);
	els.rulesChip.addEventListener("click", openBook);
	els.rulebookClose.addEventListener("click", closeBook);
	els.rulebook.addEventListener("click", (e) => { if (e.target === els.rulebook) closeBook(); });
	document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeBook(); });
}

function bindSegmented(group, attr, onPick) {
	group.querySelectorAll("button").forEach((btn) => {
		btn.addEventListener("click", () => {
			group.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
			btn.classList.add("active");
			onPick(btn.dataset[attr]);
		});
	});
}

export function readSelection() {
	return { mode: sel.mode, config: RULESETS[sel.ruleset], difficulty: sel.difficulty };
}

export function showTable() {
	els.console.classList.add("hidden");
	els.table.classList.remove("hidden");
	document.body.classList.add("playing");
}
export function showLobby() {
	els.table.classList.add("hidden");
	els.console.classList.remove("hidden");
	document.body.classList.remove("playing");
}

export function setStatus(text) { els.status.textContent = text; }

export function setHint(text, warn = false, ms = 3800) {
	els.hint.textContent = text;
	els.hint.classList.toggle("warn", warn);
	if (hintTimer) clearTimeout(hintTimer);
	if (text) hintTimer = setTimeout(() => (els.hint.textContent = ""), ms);
}

export function setRoomPill(code) {
	if (!code) { els.roomPill.classList.add("hidden"); return; }
	els.roomPill.textContent = `Room ${code}`;
	els.roomPill.classList.remove("hidden");
}

export function showWaiting(on) { els.waiting.classList.toggle("hidden", !on); }

export function reflectBranchMode(on) {
	els.branchToggle.textContent = `Fork: ${on ? "on" : "off"}`;
	els.branchToggle.classList.toggle("active", on);
}
export function reflectExplain(on) {
	els.explainToggle.textContent = `Explain: ${on ? "on" : "off"}`;
	els.explainToggle.classList.toggle("active", on);
}

export function updateBar() {
	const g = view.game;
	if (!g) return;
	els.branchToggle.classList.toggle("hidden", !g.config.allowBranch);
	els.goal.textContent = `${g.config.winLength} in a row`;

	if (els.dot) els.dot.style.background = g.current === "A" ? "var(--p-a)" : "var(--p-b)";

	if (g.winner) {
		setStatus(`Player ${g.winner} wins! 🎉`);
		return;
	}
	let text;
	if (view.mode === "hotseat") text = `Player ${g.current}'s turn`;
	else if (view.mode === "ai") text = view.seat === g.current ? "Your turn" : "Computer is thinking…";
	else if (view.seat === g.current) text = "Your turn";
	else if (view.seat) text = `Waiting for Player ${g.current}`;
	else text = `Spectating · Player ${g.current} to move`;
	const seatNote = view.mode === "online" && view.seat ? ` (you're Player ${view.seat})` : "";
	setStatus(text + seatNote);
}
