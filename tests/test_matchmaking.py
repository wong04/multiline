from src.server.matchmaking import QueueManager


def test_first_joiner_waits():
	q = QueueManager()
	assert q.join("p1", object()) is None
	assert q.waiting is True


def test_second_joiner_is_paired_with_first():
	q = QueueManager()
	h1 = object()
	assert q.join("p1", h1) is None
	partner = q.join("p2", object())
	assert partner == ("p1", h1)
	assert q.waiting is False


def test_same_token_replaces_waiting_entry():
	q = QueueManager()
	q.join("p1", object())
	assert q.join("p1", object()) is None  # reconnect, still waiting
	assert q.waiting is True


def test_leave_clears_waiting():
	q = QueueManager()
	h1 = object()
	q.join("p1", h1)
	q.leave(h1)
	assert q.waiting is False
