from pydantic import BaseModel, Field, model_validator

from ..engine import Config

MODES = ("online", "hotseat", "ai")
AI_DIFFICULTIES = ("easy", "normal", "hard")
CROSS_WIN_MODES = ("step", "union", "distinct")


class ConfigIn(BaseModel):
	size: int = Field(default=5, ge=2, le=19)
	winLength: int = Field(default=4, ge=3, le=19)
	crossWinLength: int | None = Field(default=None, ge=3, le=19)
	crossWinMode: str = "step"
	maxTimelines: int = Field(default=4, ge=1, le=6)
	allowBranch: bool = True

	@model_validator(mode="after")
	def _winnable(self) -> "ConfigIn":
		if self.winLength > self.size:
			raise ValueError("winLength cannot exceed board size")
		if self.crossWinLength is not None and self.crossWinLength > self.winLength:
			raise ValueError("crossWinLength cannot exceed winLength")
		if self.crossWinMode not in CROSS_WIN_MODES:
			raise ValueError(f"crossWinMode must be one of {CROSS_WIN_MODES}")
		return self

	def to_engine(self) -> Config:
		return Config(
			size=self.size,
			win_length=self.winLength,
			max_timelines=self.maxTimelines,
			allow_branch=self.allowBranch,
			cross_win_length=self.crossWinLength,
			cross_win_mode=self.crossWinMode,
		)


class CreateRoom(BaseModel):
	mode: str = Field(default="online")
	aiDifficulty: str = Field(default="normal")
	config: ConfigIn = Field(default_factory=ConfigIn)

	@model_validator(mode="after")
	def _check_enums(self) -> "CreateRoom":
		if self.mode not in MODES:
			raise ValueError(f"mode must be one of {MODES}")
		if self.aiDifficulty not in AI_DIFFICULTIES:
			raise ValueError(f"aiDifficulty must be one of {AI_DIFFICULTIES}")
		return self
