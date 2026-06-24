from __future__ import annotations

from enum import Enum


class Player(Enum):
	A = "A"
	B = "B"

	@property
	def other(self) -> Player:
		return Player.B if self is Player.A else Player.A
