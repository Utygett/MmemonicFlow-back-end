from dataclasses import dataclass

@dataclass(frozen=True)
class LearningSettingsSnapshot:
    base_interval_minutes: int
    level_factor: float
    streak_factor: float
    again_penalty: float
