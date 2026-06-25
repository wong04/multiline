// Canvas: deep-space window boards, glossy planet-orbs, bouncy place/branch/win.
import { myTurn, view } from "./state.js";

let canvas, ctx;
let CELL = 54;
const PAD = 26;
const GAP = 60;
const LABEL = 24;
let layout = [];
let canvasDims = { w: 0, h: 0, dpr: 0 }; // last applied backing-store size
let anim = null; // { type:"branch"|"win", start, dur, ... }
let pops = []; // [{ l, x, y, start }]
let rafQueued = false;
let prefersReduced = false;

const COLORS = {
	A: { base: "#5ec8f2", hi: "#cdeeff", deep: "#2f8fc0" },
	B: { base: "#ff9a76", hi: "#ffd6c4", deep: "#df6644" },
};
const INK = "#4a4366";
const WIN = "#ffd34a";

export function initCanvas(el) {
	canvas = el;
	ctx = canvas.getContext("2d");
	prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function computeLayout() {
	const size = view.game.config.size;
	const n = view.game.timelines.length;
	const cols = Math.min(n, 2);
	const rows = Math.ceil(n / 2);
	CELL = size >= 12 ? 34 : size >= 9 ? 44 : 52;
	// Shrink cells so the whole layout fits the container width (no overflow / CSS scaling,
	// which would break pixel->cell hit-testing). Keeps the board playable on phones.
	const avail = (canvas.parentElement && canvas.parentElement.clientWidth) || 0;
	if (avail > 60) {
		const maxBoardPx = (avail - PAD * 2 - (cols - 1) * GAP) / cols;
		const maxCell = Math.floor(maxBoardPx / size);
		if (maxCell >= 14 && maxCell < CELL) CELL = maxCell;
	}
	const boardPx = size * CELL;
	const rowH = LABEL + boardPx;
	layout = [];
	for (let l = 0; l < n; l++) {
		const col = l % 2, row = Math.floor(l / 2);
		layout[l] = { ox: PAD + col * (boardPx + GAP), oy: PAD + row * (rowH + GAP) + LABEL, boardPx };
	}
	const w = PAD * 2 + cols * boardPx + (cols - 1) * GAP;
	const h = PAD * 2 + rows * rowH + (rows - 1) * GAP;
	const dpr = window.devicePixelRatio || 1;
	// Assigning canvas.width/height reallocates + clears the backing store, so only do it
	// when the size actually changed (render() runs on every mousemove).
	if (w !== canvasDims.w || h !== canvasDims.h || dpr !== canvasDims.dpr) {
		canvas.width = w * dpr;
		canvas.height = h * dpr;
		canvas.style.width = w + "px";
		canvas.style.height = h + "px";
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		canvasDims = { w, h, dpr };
	}
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
	if (view.tutorialTarget) ensureLoop();
}

function ensureLoop() { if (!rafQueued) { rafQueued = true; requestAnimationFrame(frame); } }
function frame(now) { rafQueued = false; draw(now); if (anim || pops.length || view.tutorialTarget) ensureLoop(); }

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

	const cur = view.cursor;
	if (cur && view.kbNav && layout[cur.l] && canvas === document.activeElement) {
		const { cx, cy } = cellCenter(cur.l, cur.x, cur.y);
		if (myTurn() && isEmpty(cur.l, cur.x, cur.y)) {
			ctx.globalAlpha = 0.4;
			drawOrb(cx, cy, g.current, false, 1, view.branchMode);
			ctx.globalAlpha = 1;
		}
		ctx.save();
		ctx.strokeStyle = INK; ctx.lineWidth = 3;
		ctx.strokeRect(cx - CELL / 2 + 2, cy - CELL / 2 + 2, CELL - 4, CELL - 4);
		ctx.restore();
	}

	const tgt = view.tutorialTarget;
	if (tgt && layout[tgt.l] && isEmpty(tgt.l, tgt.x, tgt.y)) {
		const { cx, cy } = cellCenter(tgt.l, tgt.x, tgt.y);
		const pulse = 0.5 + 0.5 * Math.sin(now / 250);
		ctx.save();
		ctx.strokeStyle = WIN;
		ctx.lineWidth = 3;
		ctx.globalAlpha = 0.4 + 0.5 * pulse;
		ctx.setLineDash([4, 4]);
		ctx.beginPath(); ctx.arc(cx, cy, CELL / 2 - 3, 0, Math.PI * 2); ctx.stroke();
		ctx.restore();
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

	// soft dark-clay board panel (no hard outline)
	ctx.fillStyle = "#353160";
	roundRect(ox - 6, oy - 6, boardPx + 12, boardPx + 12, 18);
	ctx.fill();
	ctx.lineWidth = 2;
	ctx.strokeStyle = "rgba(255,255,255,0.08)";
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
		// "unbaked" ghost clay — faint matte blob, soft dashed edge
		ctx.save();
		ctx.globalAlpha *= 0.32;
		const g = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.4, r * 0.1, cx, cy, r);
		g.addColorStop(0, c.hi); g.addColorStop(1, c.base);
		ctx.fillStyle = g;
		ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
		ctx.restore();
		ctx.save();
		ctx.globalAlpha *= 0.55;
		ctx.setLineDash([4, 4]); ctx.lineWidth = 2; ctx.strokeStyle = c.base;
		ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
		ctx.restore();
		return;
	}

	// soft cast shadow under the clay ball
	ctx.save();
	ctx.shadowColor = "rgba(18,14,36,0.45)";
	ctx.shadowBlur = r * 0.5; ctx.shadowOffsetY = r * 0.22;
	const base = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.35, r * 0.15, cx, cy, r);
	base.addColorStop(0, c.hi); base.addColorStop(0.55, c.base); base.addColorStop(1, c.deep);
	ctx.fillStyle = base;
	ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
	ctx.restore();

	// matte clay modelling: dark crescent bottom-right + light wash top-left (clipped to ball)
	ctx.save();
	ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.clip();
	const lo = ctx.createRadialGradient(cx + r * 0.5, cy + r * 0.55, r * 0.2, cx + r * 0.1, cy + r * 0.15, r * 1.3);
	lo.addColorStop(0, "rgba(0,0,0,0)"); lo.addColorStop(1, "rgba(36,26,64,0.45)");
	ctx.fillStyle = lo;
	ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
	const hi = ctx.createRadialGradient(cx - r * 0.4, cy - r * 0.45, r * 0.05, cx - r * 0.2, cy - r * 0.2, r * 0.95);
	hi.addColorStop(0, "rgba(255,255,255,0.5)"); hi.addColorStop(1, "rgba(255,255,255,0)");
	ctx.fillStyle = hi;
	ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
	ctx.restore();

	// tiny soft sheen dab
	ctx.fillStyle = "rgba(255,255,255,0.5)";
	ctx.beginPath();
	ctx.ellipse(cx - r * 0.32, cy - r * 0.36, r * 0.26, r * 0.15, -0.6, 0, Math.PI * 2);
	ctx.fill();

	if (preview) {
		ctx.setLineDash([3, 4]); ctx.lineWidth = 2; ctx.strokeStyle = "rgba(255,255,255,0.85)";
		ctx.beginPath(); ctx.arc(cx, cy, r + 5, 0, Math.PI * 2); ctx.stroke();
		ctx.setLineDash([]);
	}
}

function drawSparkles(cx, cy, t) {
	const n = 5, R = (CELL / 2) * (0.6 + t);
	ctx.save();
	ctx.fillStyle = WIN;
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
	ctx.strokeStyle = WIN;
	ctx.lineWidth = 4; ctx.lineCap = "round";
	ctx.shadowColor = WIN; ctx.shadowBlur = 12;
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
	// soft clay-rope underlay, then the bright win cord
	for (const pass of [{ w: 10, s: "rgba(36,26,64,0.5)" }, { w: 6, s: WIN }]) {
		ctx.save();
		ctx.strokeStyle = pass.s; ctx.lineWidth = pass.w; ctx.lineCap = "round"; ctx.lineJoin = "round";
		ctx.beginPath();
		for (let i = 0; i < reveal; i++) { const { cx, cy } = pts[i]; i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy); }
		ctx.stroke();
		ctx.restore();
	}
	for (let i = 0; i < reveal; i++) {
		const { cx, cy } = pts[i];
		ctx.lineWidth = 3; ctx.strokeStyle = WIN;
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
