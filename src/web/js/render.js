// Canvas: deep-space window boards, glossy planet-orbs, bouncy place/branch/win.
import { myTurn, view } from "./state.js";

let canvas, ctx;
let CELL = 54;
const PAD = 26;
const GAP = 60;
const LABEL = 24;
let layout = [];
let anim = null; // { type:"branch"|"win", start, dur, ... }
let pops = []; // [{ l, x, y, start }]
let rafQueued = false;
let prefersReduced = false;

const COLORS = {
	A: { base: "#37d0ff", hi: "#e2fbff", deep: "#0a86c7" },
	B: { base: "#ff7a59", hi: "#ffe0c4", deep: "#d8421f" },
};
const INK = "#16224d";

export function initCanvas(el) {
	canvas = el;
	ctx = canvas.getContext("2d");
	prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function computeLayout() {
	const size = view.game.config.size;
	CELL = size >= 12 ? 34 : size >= 9 ? 44 : 52;
	const boardPx = size * CELL;
	const n = view.game.timelines.length;
	const rowH = LABEL + boardPx;
	const cols = Math.min(n, 2);
	const rows = Math.ceil(n / 2);
	layout = [];
	for (let l = 0; l < n; l++) {
		const col = l % 2, row = Math.floor(l / 2);
		layout[l] = { ox: PAD + col * (boardPx + GAP), oy: PAD + row * (rowH + GAP) + LABEL, boardPx };
	}
	const w = PAD * 2 + cols * boardPx + (cols - 1) * GAP;
	const h = PAD * 2 + rows * rowH + (rows - 1) * GAP;
	const dpr = window.devicePixelRatio || 1;
	canvas.width = w * dpr;
	canvas.height = h * dpr;
	canvas.style.width = w + "px";
	canvas.style.height = h + "px";
	ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function cellCenter(l, x, y) {
	const { ox, oy } = layout[l];
	return { cx: ox + x * CELL + CELL / 2, cy: oy + y * CELL + CELL / 2 };
}

export function eventCell(ev) {
	if (!view.game) return null;
	const rect = canvas.getBoundingClientRect();
	const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
	const size = view.game.config.size;
	for (let l = 0; l < layout.length; l++) {
		const { ox, oy, boardPx } = layout[l];
		if (mx >= ox && mx < ox + boardPx && my >= oy && my < oy + boardPx) {
			return { l, x: Math.floor((mx - ox) / CELL), y: Math.floor((my - oy) / CELL) };
		}
	}
	return null;
}

// Viewport coords of a cell's center (CSS px). Read-only; used by the playtest harness.
export function cellClientPoint(l, x, y) {
	if (!view.game || !layout[l]) return null;
	const { cx, cy } = cellCenter(l, x, y);
	const rect = canvas.getBoundingClientRect();
	return { x: rect.left + cx, y: rect.top + cy };
}

const easeOutBack = (t) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const easeOut = (t) => 1 - Math.pow(1 - t, 3);

export function render() {
	if (!view.game) return;
	computeLayout();
	draw(performance.now());
}

function ensureLoop() { if (!rafQueued) { rafQueued = true; requestAnimationFrame(frame); } }
function frame(now) { rafQueued = false; draw(now); if (anim || pops.length) ensureLoop(); }

function draw(now) {
	const g = view.game;
	const size = g.config.size;
	ctx.clearRect(0, 0, canvas.width, canvas.height);

	const branchProg = anim && anim.type === "branch" ? Math.min(1, (now - anim.start) / anim.dur) : 1;
	if (anim && anim.type === "branch" && branchProg >= 1) anim = null;
	pops = pops.filter((p) => now - p.start < 420);

	const newIndex = anim && anim.type === "branch" ? anim.newIndex : -1;

	g.timelines.forEach((stones, l) => {
		ctx.save();
		if (l === newIndex) {
			const p = easeOutBack(branchProg);
			const { ox, oy, boardPx } = layout[l];
			const cx = ox + boardPx / 2, cy = oy + boardPx / 2;
			ctx.globalAlpha = Math.min(1, branchProg * 1.5);
			ctx.translate(cx, cy);
			ctx.scale(0.4 + 0.6 * p, 0.4 + 0.6 * p);
			ctx.translate(-cx, -cy);
		}
		drawChart(l, size, stones, now);
		ctx.restore();
	});

	if (anim && anim.type === "branch" && branchProg < 1 && anim.srcIndex >= 0) {
		drawThread(anim.srcIndex, anim.newIndex, easeOut(branchProg));
	}

	if (view.hover && myTurn() && isEmpty(view.hover.l, view.hover.x, view.hover.y)) {
		const { cx, cy } = cellCenter(view.hover.l, view.hover.x, view.hover.y);
		ctx.globalAlpha = 0.45;
		drawOrb(cx, cy, g.current, false, 1, view.branchMode);
		ctx.globalAlpha = 1;
	}

	if (g.winningLine) {
		const winProg = anim && anim.type === "win" ? Math.min(1, (now - anim.start) / anim.dur) : 1;
		drawWinLine(g.winningLine, easeOut(winProg), now);
		if (anim && anim.type === "win" && (now - anim.start) / anim.dur >= 1.3) anim = null;
	}
}

function drawChart(l, size, stones, now) {
	const { ox, oy, boardPx } = layout[l];

	ctx.fillStyle = "rgba(226,251,255,0.8)";
	ctx.font = "700 12px 'Fredoka', sans-serif";
	ctx.textBaseline = "alphabetic";
	ctx.fillText(l === 0 ? "Timeline 0" : `Timeline ${l}`, ox, oy - 8);

	// window panel
	ctx.fillStyle = "#163063";
	roundRect(ox - 5, oy - 5, boardPx + 10, boardPx + 10, 12);
	ctx.fill();
	ctx.lineWidth = 3;
	ctx.strokeStyle = INK;
	ctx.stroke();

	// faint star speckle (deterministic per board)
	ctx.fillStyle = "rgba(255,255,255,0.35)";
	let seed = (l + 1) * 9301;
	for (let i = 0; i < 14; i++) {
		seed = (seed * 49297 + 233280) % 233280;
		const sx = ox + (seed / 233280) * boardPx;
		seed = (seed * 49297 + 233280) % 233280;
		const sy = oy + (seed / 233280) * boardPx;
		ctx.fillRect(sx, sy, 1.5, 1.5);
	}

	// grid
	ctx.strokeStyle = "rgba(255,255,255,0.14)";
	ctx.lineWidth = 1;
	for (let i = 0; i <= size; i++) {
		ctx.beginPath();
		ctx.moveTo(ox + i * CELL, oy); ctx.lineTo(ox + i * CELL, oy + boardPx);
		ctx.moveTo(ox, oy + i * CELL); ctx.lineTo(ox + boardPx, oy + i * CELL);
		ctx.stroke();
	}

	for (const s of stones) {
		const { cx, cy } = cellCenter(l, s.x, s.y);
		let scale = 1;
		const pop = pops.find((p) => p.l === l && p.x === s.x && p.y === s.y);
		if (pop) {
			const t = Math.min(1, (now - pop.start) / 360);
			scale = easeOutBack(t);
			drawSparkles(cx, cy, t);
		}
		drawOrb(cx, cy, s.player, s.inherited, scale, false);
	}
}

function drawOrb(cx, cy, player, inherited, scale, preview) {
	const c = COLORS[player];
	const r = (CELL / 2 - 5) * scale;
	if (r <= 0) return;

	if (inherited) {
		ctx.globalAlpha *= 0.4;
		const g = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.4, r * 0.1, cx, cy, r);
		g.addColorStop(0, c.hi); g.addColorStop(1, c.base);
		ctx.fillStyle = g;
		ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
		ctx.globalAlpha /= 0.4;
		ctx.setLineDash([4, 3]); ctx.lineWidth = 2; ctx.strokeStyle = c.base;
		ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
		ctx.setLineDash([]);
		return;
	}

	ctx.save();
	ctx.shadowColor = "rgba(8,16,40,0.5)";
	ctx.shadowBlur = 6; ctx.shadowOffsetY = 3;
	const g = ctx.createRadialGradient(cx - r * 0.35, cy - r * 0.42, r * 0.1, cx, cy, r);
	g.addColorStop(0, c.hi); g.addColorStop(0.5, c.base); g.addColorStop(1, c.deep);
	ctx.fillStyle = g;
	ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
	ctx.restore();

	ctx.lineWidth = Math.max(2, r * 0.14);
	ctx.strokeStyle = INK;
	ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();

	// glossy highlight
	ctx.fillStyle = "rgba(255,255,255,0.75)";
	ctx.beginPath();
	ctx.ellipse(cx - r * 0.3, cy - r * 0.36, r * 0.3, r * 0.18, -0.6, 0, Math.PI * 2);
	ctx.fill();

	if (preview) {
		ctx.setLineDash([3, 4]); ctx.lineWidth = 2; ctx.strokeStyle = "#fff";
		ctx.beginPath(); ctx.arc(cx, cy, r + 5, 0, Math.PI * 2); ctx.stroke();
		ctx.setLineDash([]);
	}
}

function drawSparkles(cx, cy, t) {
	const n = 5, R = (CELL / 2) * (0.6 + t);
	ctx.save();
	ctx.fillStyle = "#ffe24a";
	ctx.globalAlpha = 1 - t;
	for (let i = 0; i < n; i++) {
		const a = (i / n) * Math.PI * 2 + t;
		const x = cx + Math.cos(a) * R, y = cy + Math.sin(a) * R;
		ctx.beginPath(); ctx.arc(x, y, 2.5 * (1 - t) + 1, 0, Math.PI * 2); ctx.fill();
	}
	ctx.restore();
}

function drawThread(srcL, dstL, p) {
	if (!layout[srcL] || !layout[dstL]) return;
	const a = layout[srcL], b = layout[dstL];
	const x1 = a.ox + a.boardPx / 2, y1 = a.oy + a.boardPx / 2;
	const x2 = b.ox + b.boardPx / 2, y2 = b.oy + b.boardPx / 2;
	ctx.save();
	ctx.strokeStyle = "#ffe24a";
	ctx.lineWidth = 4; ctx.lineCap = "round";
	ctx.shadowColor = "#ffe24a"; ctx.shadowBlur = 12;
	ctx.beginPath();
	ctx.moveTo(x1, y1);
	const midx = x1 + (x2 - x1) * p, midy = y1 + (y2 - y1) * p - Math.sin(p * Math.PI) * 22;
	ctx.quadraticCurveTo(midx, midy, x1 + (x2 - x1) * p, y1 + (y2 - y1) * p);
	ctx.stroke();
	ctx.restore();
}

function drawWinLine(cells, p, now) {
	const pts = cells.map((c) => cellCenter(c.l, c.x, c.y));
	const reveal = Math.max(1, Math.floor(pts.length * p));
	const pulse = 1 + 0.08 * Math.sin(now / 140);
	// ink underlay
	for (const pass of [{ w: 9, s: INK }, { w: 5, s: "#ffe24a" }]) {
		ctx.save();
		ctx.strokeStyle = pass.s; ctx.lineWidth = pass.w; ctx.lineCap = "round"; ctx.lineJoin = "round";
		ctx.beginPath();
		for (let i = 0; i < reveal; i++) { const { cx, cy } = pts[i]; i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy); }
		ctx.stroke();
		ctx.restore();
	}
	for (let i = 0; i < reveal; i++) {
		const { cx, cy } = pts[i];
		ctx.lineWidth = 3; ctx.strokeStyle = "#ffe24a";
		ctx.beginPath(); ctx.arc(cx, cy, (CELL / 2 - 3) * pulse, 0, Math.PI * 2); ctx.stroke();
	}
}

function roundRect(x, y, w, h, r) {
	ctx.beginPath();
	ctx.moveTo(x + r, y);
	ctx.arcTo(x + w, y, x + w, y + h, r);
	ctx.arcTo(x + w, y + h, x, y + h, r);
	ctx.arcTo(x, y + h, x, y, r);
	ctx.arcTo(x, y, x + w, y, r);
	ctx.closePath();
}

function isEmpty(l, x, y) { return !view.game.timelines[l].some((s) => s.x === x && s.y === y); }

export function animatePlace(l, x, y) {
	pops.push({ l, x, y, start: performance.now() });
	ensureLoop();
}

export function animateBranch(srcIndex, newIndex) {
	if (prefersReduced) { render(); return; }
	computeLayout();
	anim = { type: "branch", start: performance.now(), dur: 700, srcIndex, newIndex };
	ensureLoop();
}

export function animateWin() {
	if (prefersReduced) { render(); return; }
	computeLayout();
	anim = { type: "win", start: performance.now(), dur: 650 };
	ensureLoop();
}
