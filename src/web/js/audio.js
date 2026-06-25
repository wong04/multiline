// Cartoony sound — all synthesized with the Web Audio API (no asset files): pop SFX on
// clicks/placements, a happy fanfare on a win, and a light looping background tune.
// A single mute toggle (persisted) governs everything; audio only starts after a gesture.

let ctx = null;
let muted = localStorage.getItem("multiline-muted") === "1";
let musicTimer = null;
let musicGain = null;
let unlocked = false;

function ac() {
	if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
	if (ctx.state === "suspended") ctx.resume();
	return ctx;
}

// A short pitched blip with a gain envelope. `rise` makes the bouncy "pop".
function blip(freq, { type = "triangle", dur = 0.16, peak = 0.22, rise = true, dest = null } = {}) {
	const c = ac();
	const t = c.currentTime;
	const o = c.createOscillator();
	const g = c.createGain();
	o.type = type;
	o.frequency.setValueAtTime(freq, t);
	if (rise) o.frequency.exponentialRampToValueAtTime(freq * 2.1, t + dur * 0.5);
	g.gain.setValueAtTime(0.0001, t);
	g.gain.exponentialRampToValueAtTime(peak, t + 0.012);
	g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
	o.connect(g).connect(dest || c.destination);
	o.start(t);
	o.stop(t + dur + 0.02);
}

export function pop() {
	if (muted) return;
	blip(420 + Math.random() * 140, { peak: 0.2, dur: 0.14 });
}

export function plop() {
	if (muted) return;
	blip(300 + Math.random() * 60, { type: "sine", rise: false, dur: 0.18, peak: 0.18 });
}

export function fanfare() {
	if (muted) return;
	const notes = [523.25, 659.25, 783.99, 1046.5]; // C-E-G-C major arpeggio
	const c = ac();
	notes.forEach((f, i) => {
		const t = c.currentTime + i * 0.1;
		const o = c.createOscillator();
		const g = c.createGain();
		o.type = "triangle";
		o.frequency.setValueAtTime(f, t);
		g.gain.setValueAtTime(0.0001, t);
		g.gain.exponentialRampToValueAtTime(0.26, t + 0.02);
		g.gain.exponentialRampToValueAtTime(0.0001, t + 0.32);
		o.connect(g).connect(c.destination);
		o.start(t);
		o.stop(t + 0.34);
	});
}

// --- background music: a cheerful pentatonic loop + soft bass ---
const N = { C: 523.25, D: 587.33, E: 659.25, G: 783.99, A: 880.0, c: 1046.5, _: 0 };
const MELODY = [N.C, N.E, N.G, N.E, N.A, N.G, N.E, N.D, N.C, N.E, N.G, N.c, N.A, N.G, N.E, N._];
const BASS = [N.C / 4, N.G / 4, N.A / 4, N.E / 4];
const BEAT = 0.26;

function note(freq, t, dur, peak, type) {
	if (!freq) return;
	const c = ctx;
	const o = c.createOscillator();
	const g = c.createGain();
	o.type = type;
	o.frequency.value = freq;
	g.gain.setValueAtTime(0.0001, t);
	g.gain.exponentialRampToValueAtTime(peak, t + 0.03);
	g.gain.exponentialRampToValueAtTime(0.0001, t + dur * 0.92);
	o.connect(g).connect(musicGain);
	o.start(t);
	o.stop(t + dur);
}

function scheduleLoop() {
	const c = ctx;
	let t = c.currentTime + 0.06;
	MELODY.forEach((f, i) => {
		note(f, t + i * BEAT, BEAT, 0.5, "triangle");
		if (i % 4 === 0) note(BASS[(i / 4) % BASS.length], t + i * BEAT, BEAT * 3.5, 0.6, "sine");
	});
	const loopLen = MELODY.length * BEAT;
	musicTimer = setTimeout(scheduleLoop, loopLen * 1000 - 80);
}

function startMusic() {
	if (muted || musicTimer) return;
	const c = ac();
	if (!musicGain) {
		musicGain = c.createGain();
		musicGain.gain.value = 0.06; // gentle background level
		musicGain.connect(c.destination);
	}
	scheduleLoop();
}

function stopMusic() {
	if (musicTimer) { clearTimeout(musicTimer); musicTimer = null; }
}

// Call on the first user gesture (browsers block audio before one).
export function unlock() {
	if (unlocked) return;
	unlocked = true;
	ac();
	startMusic();
}

export function toggleMute() {
	muted = !muted;
	localStorage.setItem("multiline-muted", muted ? "1" : "0");
	if (muted) stopMusic();
	else startMusic();
	return muted;
}

export function isMuted() { return muted; }
