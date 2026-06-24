// Three staged lessons, each played on a real hotseat room so the engine stays
// authoritative. Goals auto-detect to celebrate; "Next" always lets you advance.
import { setHint } from "./ui.js";

const LESSONS = [
	{
		ruleset: "classic",
		title: "Make a line",
		body: "This is the origin timeline. Take turns placing stars (you control both colours). Line up FIVE in a row — across, down, or diagonally — to win. Give it a try.",
		goal: (g) => !!g.winner,
		done: "That's a line. The whole game is built on this.",
	},
	{
		ruleset: "branch",
		title: "Fork a timeline",
		body: "Switch on “Chart timeline” (top-right), then click an empty cell. A NEW timeline forks off — a copy of this one, its stars carried over as dim echoes. Make one fork and watch it appear.",
		goal: (g) => g.timelines.length > 1,
		done: "A new universe! Echoes are inherited stars; freshly-placed stars are bright.",
	},
	{
		ruleset: "branch",
		title: "Win across universes",
		body: "A winning line can step DIAGONALLY from one chart into the next. On this small board (3-in-a-row, 3 timelines) build a diagonal that threads across adjacent timelines. Land a cross-timeline win.",
		goal: (g) => !!g.winner && new Set((g.winningLine || []).map((c) => c.l)).size > 1,
		done: "You won across the multiverse. Now you're playing 5-dimensionally.",
	},
];

let step = 0;
let solved = false;
let api = null; // { launch(config), exit() }
let els = {};

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

async function load() {
	solved = false;
	const lesson = LESSONS[step];
	await api.launch(lesson.ruleset);
	els.root.classList.remove("hidden");
	els.step.textContent = `Lesson ${step + 1} / ${LESSONS.length}`;
	els.title.textContent = lesson.title;
	els.body.textContent = lesson.body;
	els.next.textContent = step === LESSONS.length - 1 ? "Finish ▸" : "Skip ahead ▸";
}

function advance() {
	if (step >= LESSONS.length - 1) { finish(); return; }
	step += 1;
	load();
}

function finish() {
	els.root.classList.add("hidden");
	api.exit();
	setHint("Tutorial complete — you're ready. Choose a mode to play for real.");
}

// Called by the main dispatcher on every state update while in the tutorial.
export function onState(game) {
	if (solved || !game) return;
	const lesson = LESSONS[step];
	if (lesson.goal(game)) {
		solved = true;
		setHint("✦ " + lesson.done);
		els.next.textContent = step === LESSONS.length - 1 ? "Finish ▸" : "Next lesson ▸";
		els.next.classList.add("glow");
	}
}
