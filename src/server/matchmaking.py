"""Quick-match queue: holds at most one waiting client and pairs the next arrival.

Kept free of web-framework types so it's unit-testable; the caller supplies an opaque
`handle` (e.g. a WebSocket) and does the actual I/O on the returned partner.
"""


class QueueManager:
	def __init__(self):
		self._waiting: tuple[str, object] | None = None

	def join(self, token: str, handle: object) -> tuple[str, object] | None:
		"""Add a client. Returns the partner to pair with, or None if now waiting."""
		if self._waiting is None or self._waiting[0] == token:
			self._waiting = (token, handle)
			return None
		partner = self._waiting
		self._waiting = None
		return partner

	def leave(self, handle: object) -> None:
		if self._waiting is not None and self._waiting[1] is handle:
			self._waiting = None

	@property
	def waiting(self) -> bool:
		return self._waiting is not None
