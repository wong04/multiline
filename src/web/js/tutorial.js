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
		body: "Two of your planets already line up across boards. A third in a single board is too short to win — but FORK (top-right) and drop your planet on the glowing cell. That finishes a 3-long diagonal across timelines: a win you simply can't make in one board.",
		// Pre-seed the position (hotseat plays both colours). After this it's your move:
		// you have A at (0,0) in TL0 and (1,1) in TL1 — forking at (2,2) completes the
		// cross-timeline diagonal. Placing (not forking) can't reach the 3rd timeline.
		setup: [
			{ type: "place", timeline: 0, x: 0, y: 0 },  // A
			{ type: "place", timeline: 0, x: 5, y: 5 },  // B (harmless; not carried into forks)
			{ type: "branch", source: 0, x: 1, y: 1 },   // A -> TL1 with A's planets only
			{ type: "place", timeline: 0, x: 0, y: 5 },  // B (harmless)
		],
		target: { l: 1, x: 2, y: 2 },
		goal: (g) => !!g.winner && new Set((g.winningLine || []).map((c) => c.l)).size > 1,
		done: "A cross-timeline win — only possible because you forked. THAT'S why you fork.",
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
	branch: "Branching · 4 in a board, or 3 across timelines",
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
