// Transport: REST room creation + WebSocket game/queue sockets.
import { resetForConnect, view } from "./state.js";

export function clientToken() {
	let t = localStorage.getItem("multiline-token");
	if (!t) {
		t = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
		localStorage.setItem("multiline-token", t);
	}
	return t;
}

function wsUrl(path) {
	const proto = location.protocol === "https:" ? "wss" : "ws";
	const sep = path.includes("?") ? "&" : "?";
	return `${proto}://${location.host}${path}${sep}token=${encodeURIComponent(clientToken())}`;
}

export async function createRoom({ mode, config, aiDifficulty }) {
	const res = await fetch("/api/rooms", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ mode, config, aiDifficulty }),
	});
	if (!res.ok) {
		let message = "could not create game";
		try {
			const j = await res.json();
			message = j.error || JSON.stringify(j);
		} catch {}
		throw new Error(message);
	}
	return (await res.json()).code;
}

export function connectRoom(code, handlers) {
	resetForConnect();
	const ws = new WebSocket(wsUrl(`/ws/${code}`));
	view.ws = ws;
	view.code = code;
	ws.onmessage = (e) => handlers.onMessage(JSON.parse(e.data));
	ws.onclose = () => handlers.onClose && handlers.onClose();
	ws.onerror = () => handlers.onError && handlers.onError();
	return ws;
}

export function connectQueue(handlers) {
	const ws = new WebSocket(wsUrl("/ws/queue"));
	view.queueWs = ws;
	ws.onmessage = (e) => handlers.onMessage(JSON.parse(e.data));
	ws.onclose = () => handlers.onClose && handlers.onClose();
	return ws;
}

export function send(obj) {
	if (view.ws && view.ws.readyState === WebSocket.OPEN) {
		view.ws.send(JSON.stringify(obj));
	}
}

export function closeRoom() {
	if (view.ws) {
		view.intentional = true;
		view.ws.close();
		view.ws = null;
	}
}

export function closeQueue() {
	if (view.queueWs) {
		view.queueWs.close();
		view.queueWs = null;
	}
}
