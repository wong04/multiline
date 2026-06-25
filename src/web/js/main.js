// Bootstrap: wire lobby actions, message dispatch, canvas input, playful atmosphere.
import * as net from "./net.js";
import * as render from "./render.js";
import * as tutorial from "./tutorial.js";
import * as ui from "./ui.js";
import { isEmptyCell, myTurn, view } from "./state.js";

const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- message dispatch ----------
function newlyPlaced(prev, cur) {
	const out = [];
	for (let l = 0; l < cur.timelines.length; l++) {
		const before = prev && prev.timelines[l] ? prev.timelines[l] : [];
		const seen = new Set(before.map((s) => s.x + "," + s.y));
		for (const s of cur.timelines[l]) {
			if (!s.inherited && !seen.has(s.x + "," + s.y)) out.push({ l, x: s.x, y: s.y });
		}
	}
	return out;
}

function handleMessage(msg) {
	if (msg.type === "joined") {
		view.seat = msg.seat;
		view.mode = msg.mode;
		ui.updateBar();
	} else if (msg.type === "state") {
		const prev = view.game;
		view.game = msg;
		const grew = prev && msg.timelines.length > prev.timelines.length;
		const newWin = msg.winner && !(prev && prev.winner);
		if (newWin) render.animateWin();
		else if (grew) render.animateBranch(msg.timelines.length - 2, msg.timelines.length - 1);
		else render.render();
		if (prev) newlyPlaced(prev, msg).forEach((c) => render.animatePlace(c.l, c.x, c.y));
		if (grew) setBranchMode(false);
		if (newWin && !reduced) spawnConfetti();
		ui.updateBar();
		if (view.inTutorial) tutorial.onState(msg);
	} else if (msg.type === "error") {
		ui.setHint("✖ " + msg.message, true);
	}
	// "ping" + unknown types ignored.
}

const roomHandlers = {
	onMessage: handleMessage,
	onClose: () => { if (!view.intentional) ui.setStatus("Connection lost — refresh to rejoin."); },
	onError: () => { if (!view.intentional) ui.setStatus("Connection error."); },
};

// ---------- connection helpers ----------
function connectToRoom(code, showPill) {
	net.connectRoom(code, roomHandlers);
	ui.showTable();
	ui.setStatus("Connecting…");
	ui.setRoomPill(showPill ? code : null);
	ui.reflectBranchMode(false);
	ui.reflectExplain(view.explain);
	if (showPill) net.saveSession(code, view.mode || "online");  // online rooms can be rejoined
}

// On load, rejoin an online game left by an accidental reload (seat kept by token).
async function attemptResume() {
	const s = net.loadSession();
	if (!s || !s.code) return;
	const info = await net.fetchRoom(s.code).catch(() => null);
	if (!info || (info.state && info.state.winner)) { net.clearSession(); return; }
	view.mode = s.mode || "online";
	connectToRoom(s.code, true);
	ui.setHint("Reconnected to your game.");
}

function setBranchMode(on) {
	if (on && view.game && !view.game.config.allowBranch) return;
	view.branchMode = on;
	ui.reflectBranchMode(on);
}

// ---------- lobby actions ----------
async function begin() {
	const { mode, config, difficulty } = ui.readSelection();
	try {
		const code = await net.createRoom({ mode, config, aiDifficulty: difficulty });
		view.mode = mode;
		connectToRoom(code, mode === "online");
		if (mode === "online") ui.setHint(`Share code ${code} with your opponent.`);
	} catch (e) {
		ui.setHint("✖ " + e.message, true);
	}
}

function join() {
	const code = document.getElementById("join-code").value.trim().toUpperCase();
	if (!code) return;
	view.mode = "online";
	connectToRoom(code, true);
}

function quickmatch() {
	ui.showWaiting(true);
	net.connectQueue({
		onMessage: (msg) => {
			if (msg.type === "matched") {
				ui.showWaiting(false);
				net.closeQueue();
				view.mode = "online";
				connectToRoom(msg.code, true);
				ui.setHint("Opponent found — good luck!");
			}
		},
		onClose: () => ui.showWaiting(false),
	});
}

function cancelQueue() { net.closeQueue(); ui.showWaiting(false); }

function leave() {
	net.closeRoom();
	net.closeQueue();
	net.clearSession();
	view.tutorialTarget = null;
	if (view.inTutorial) {
		view.inTutorial = false;
		document.getElementById("tutorial").classList.add("hidden");
	}
	ui.showLobby();
	ui.setRoomPill(null);
	ui.showWaiting(false);
}

function help() { view.inTutorial = true; tutorial.start(); }

// ---------- canvas input ----------
function setupCanvas() {
	const canvas = document.getElementById("board");
	render.initCanvas(canvas);
	canvas.addEventListener("mousemove", (ev) => {
		view.hover = render.eventCell(ev);
		const over = view.hover && view.game && isEmptyCell(view.hover.l, view.hover.x, view.hover.y) && myTurn();
		if (over && view.explain) {
			ui.setHint(view.branchMode
				? "Forks a new timeline (a copy of this board) and places your planet here."
				: "Drops your planet here.", false, 1500);
		}
		render.render();
	});
	canvas.addEventListener("mouseleave", () => { view.hover = null; render.render(); });
	canvas.addEventListener("click", (ev) => {
		const hit = render.eventCell(ev);
		if (hit) commitMove(hit.l, hit.x, hit.y);
	});

	// Keyboard play (accessibility): arrows move a cursor across cells/timelines, Enter commits.
	canvas.addEventListener("focus", () => {
		if (!view.cursor && view.game) {
			const c = view.game.config.size >> 1;
			view.cursor = { l: 0, x: c, y: c };
		}
		render.render();
		announceCursor();
	});
	canvas.addEventListener("blur", () => render.render());
	canvas.addEventListener("keydown", onBoardKey);
}

function commitMove(l, x, y) {
	if (!myTurn()) { ui.setHint("Not your turn yet!", true, 1800); return; }
	if (!isEmptyCell(l, x, y)) { ui.setHint("That spot's taken — pick an empty cell.", true, 1600); return; }
	if (view.branchMode) {
		if (view.game.timelines.length >= view.game.config.maxTimelines) {
			ui.setHint("Timeline limit reached — can't fork more.", true);
			return;
		}
		net.send({ type: "branch", source: l, x, y });
	} else {
		net.send({ type: "place", timeline: l, x, y });
	}
}

function onBoardKey(e) {
	if (!view.game) return;
	const size = view.game.config.size;
	const n = view.game.timelines.length;
	let c = view.cursor || { l: 0, x: size >> 1, y: size >> 1 };
	if (e.key === "ArrowUp") c = { ...c, y: Math.max(0, c.y - 1) };
	else if (e.key === "ArrowDown") c = { ...c, y: Math.min(size - 1, c.y + 1) };
	else if (e.key === "ArrowLeft") c = c.x > 0 ? { ...c, x: c.x - 1 } : (c.l > 0 ? { l: c.l - 1, x: size - 1, y: c.y } : c);
	else if (e.key === "ArrowRight") c = c.x < size - 1 ? { ...c, x: c.x + 1 } : (c.l < n - 1 ? { l: c.l + 1, x: 0, y: c.y } : c);
	else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); commitMove(c.l, c.x, c.y); return; }
	else return;
	e.preventDefault();
	view.cursor = c;
	render.render();
	announceCursor();
}

function announceCursor() {
	const c = view.cursor;
	if (!c || !view.game) return;
	const live = document.getElementById("board-live");
	if (!live) return;
	const stone = view.game.timelines[c.l].find((s) => s.x === c.x && s.y === c.y);
	const what = stone ? `${stone.player}'s planet${stone.inherited ? " (echo)" : ""}` : "empty";
	live.textContent = `Timeline ${c.l}, column ${c.x + 1}, row ${c.y + 1}: ${what}`;
}

// ---------- playful atmosphere ----------
function setupAtmosphere() {
	// Skip the blob/parallax on touch (no hover) and when motion is reduced.
	if (reduced || window.matchMedia("(pointer: coarse)").matches) return;
	const cursor = document.getElementById("cursor");
	const scene = document.querySelector(".scene");
	let raf = null, mx = 0, my = 0;
	window.addEventListener("pointermove", (e) => {
		mx = e.clientX; my = e.clientY;
		if (raf) return;
		raf = requestAnimationFrame(() => {
			raf = null;
			if (cursor) { cursor.style.setProperty("--mx", mx + "px"); cursor.style.setProperty("--my", my + "px"); }
			if (scene) {
				const dx = (mx / window.innerWidth - 0.5) * 30;
				const dy = (my / window.innerHeight - 0.5) * 30;
				scene.style.setProperty("--px", (-dx).toFixed(1));
				scene.style.setProperty("--py", (-dy).toFixed(1));
			}
		});
	});
	window.addEventListener("pointerdown", () => cursor && cursor.classList.add("down"));
	window.addEventListener("pointerup", () => cursor && cursor.classList.remove("down"));
	document.addEventListener("pointerover", (e) => {
		if (!cursor) return;
		const hot = e.target.closest("button, select, input, a, .link, .segmented button, canvas");
		cursor.classList.toggle("hot", !!hot);
	});
}

const CONFETTI = ["#37d0ff", "#ff7a59", "#ffd23f", "#6ef0c0", "#ff8fcf", "#9b8cff"];
function spawnConfetti() {
	for (let i = 0; i < 80; i++) {
		const c = document.createElement("div");
		c.className = "confetti-piece";
		c.style.left = Math.random() * 100 + "vw";
		c.style.background = CONFETTI[i % CONFETTI.length];
		c.style.animationDuration = 1.8 + Math.random() * 1.6 + "s";
		c.style.animationDelay = Math.random() * 0.4 + "s";
		c.style.transform = `rotate(${Math.random() * 360}deg)`;
		document.body.appendChild(c);
		setTimeout(() => c.remove(), 3800);
	}
}

// ---------- boot ----------
function boot() {
	ui.initUI({
		begin, join, quickmatch, cancelQueue,
		branchToggle: () => {
			setBranchMode(!view.branchMode);
			ui.setHint(view.branchMode
				? "Fork mode on — click an empty cell to spin off a new timeline!"
				: "Back to dropping planets.", false, 2200);
		},
		explainToggle: () => { view.explain = !view.explain; ui.reflectExplain(view.explain); },
		reset: () => { setBranchMode(false); net.send({ type: "reset" }); },
		leave, help,
	});
	tutorial.initTutorial({
		launch: (ruleset) => {
			net.closeRoom();
			view.mode = "hotseat";
			return net.createRoom({ mode: "hotseat", config: ui.RULESETS[ruleset], aiDifficulty: "normal" })
				.then((code) => connectToRoom(code, false));
		},
		play: (move) => net.send(move),
		exit: () => { view.inTutorial = false; view.tutorialTarget = null; net.closeRoom(); ui.showLobby(); ui.setRoomPill(null); },
	});
	setupCanvas();
	setupAtmosphere();
	window.addEventListener("resize", () => { if (view.game) render.render(); });

	// Read-only hook for the playtest harness: inspect state + locate cells. No behaviour change.
	window.__multiline = { view, cellPoint: render.cellClientPoint };

	attemptResume();

	const loader = document.getElementById("loader");
	const hide = () => loader && loader.classList.add("gone");
	if (document.readyState === "complete") setTimeout(hide, 700);
	else window.addEventListener("load", () => setTimeout(hide, 700));
}

boot();
