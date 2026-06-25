// Three staged lessons, each played on a real hotseat room so the engine stays
// authoritative. Goals auto-detect to celebrate; "Next" always lets you advance.
import { setHint } from "./ui.js";
import * as render from "./render.js";
import { view } from "./state.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const LESSONS = [
	{
		ruleset: "classic",
		title: "Make a line",
		body: "This is the origin timeline. Take turns placing planets (you control both colours). Line up FIVE in a row — across, down, or diagonally — to win. Give it a try.",
		goal: (g) => !!g.winner,
		done: "That's a line. The whole game is built on this.",
	},
	{
		ruleset: "branch",
		title: "Fork a timeline",
		body: "Switch on “Fork” (top-right), then click an empty cell. A NEW timeline forks off — a copy of this one, its planets carried over as dim echoes. Make one fork and watch it appear.",
		goal: (g) => g.timelines.length > 1,
		done: "A new universe! Echoes are inherited planets; freshly-placed planets are bright.",
	},
	{
		ruleset: "branch",
		title: "Why fork? To win.",
		body: "Your diagonal is split across boards: three planets here in Timeline 0, and one at (1,1) sitting over in Timeline 1 (you forked earlier to put it there). Fork the glowing cell to finish a diagonal of 4 across your timelines — a win you can't make in any single board.",
		// Pre-seed the position (hotseat plays both colours). Forks are contestable (copy the
		// whole board), so the win must be a *split* diagonal: (1,1) lives ONLY in TL1, the rest
		// in TL0 — so completing (2,2) can never be an in-board 4, only a cross win. After setup
		// it's A's move; forking TL0 at (2,2) finishes the diagonal across timelines.
		setup: [
			{ type: "place", timeline: 0, x: 0, y: 0 },  // A (0,0)
			{ type: "place", timeline: 0, x: 5, y: 5 },  // B
			{ type: "branch", source: 0, x: 1, y: 1 },   // A -> TL1 (carries (0,0)) + places (1,1)
			{ type: "place", timeline: 0, x: 5, y: 4 },  // B
			{ type: "place", timeline: 0, x: 3, y: 3 },  // A (3,3) in TL0 only — NOT carried into TL1
			{ type: "place", timeline: 0, x: 4, y: 4 },  // B
		],
		target: { l: 0, x: 2, y: 2 },
		goal: (g) => !!g.winner && new Set((g.winningLine || []).map((c) => c.l)).size > 1,
		done: "A cross-timeline win — your diagonal lived across two boards at once. THAT'S why you fork.",
	},
];

let step = 0;
let solved = false;
let api = null; // { launch(config), play(move), exit() }
let els = {};
let pendingSetup = null; // scripted moves to seed a puzzle, applied on first state
let setupStarted = false;

export function initTutorial(callbacks) {
	api = callbacks;
	els = {
		root: document.getElementById("tutorial"),
		step: document.getElementById("tutorial-step"),
		title: document.getElementById("tutorial-title"),
		body: document.getElementById("tutorial-body"),
		next: document.getElementById("tutorial-next"),
		skip: document.getElementById("tutorial-skip"),
	};
	els.next.addEventListener("click", advance);
	els.skip.addEventListener("click", finish);
}

export function start() {
	step = 0;
	load();
}

// Each ruleset's goal, shown so learners aren't surprised the row length changes.
const RULESET_GOAL = {
	classic: "Classic · 5 in a row",
	branch: "Branching · 4 in a board, or a diagonal of 4 across different timelines",
};

async function load() {
	solved = false;
	view.tutorialTarget = null;
	const lesson = LESSONS[step];
	pendingSetup = lesson.setup ? lesson.setup.slice() : null;
	setupStarted = false;
	await api.launch(lesson.ruleset);
	els.root.classList.remove("hidden");
	els.next.classList.remove("glow");
	const goal = RULESET_GOAL[lesson.ruleset] || lesson.ruleset;
	els.step.textContent = `Lesson ${step + 1} / ${LESSONS.length} · ${goal}`;
	els.title.textContent = lesson.title;
	els.body.textContent = lesson.body;
	els.next.textContent = step === LESSONS.length - 1 ? "Finish ▸" : "Skip ahead ▸";
}

async function runSetup() {
	const moves = pendingSetup;
	pendingSetup = null;
	for (const mv of moves) {
		api.play(mv);
		await sleep(300);
	}
	const lesson = LESSONS[step];
	if (lesson.target) {
		view.tutorialTarget = lesson.target;
		render.render();
		setHint("Turn on Fork, then drop your planet on the glowing cell to win.", false, 6000);
	}
}

function advance() {
	if (step >= LESSONS.length - 1) { finish(); return; }
	step += 1;
	load();
}

function finish() {
	els.root.classList.add("hidden");
	view.tutorialTarget = null;
	api.exit();
	setHint("Tutorial complete — you're ready. Choose a mode to play for real.");
}

// Called by the main dispatcher on every state update while in the tutorial.
export function onState(game) {
	if (pendingSetup && !setupStarted) {
		setupStarted = true;
		runSetup();
		return;
	}
	if (solved || !game) return;
	const lesson = LESSONS[step];
	if (lesson.goal(game)) {
		solved = true;
		view.tutorialTarget = null;
		setHint("✦ " + lesson.done);
		els.next.textContent = step === LESSONS.length - 1 ? "Finish ▸" : "Next lesson ▸";
		els.next.classList.add("glow");
	}
}
