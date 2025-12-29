from dataclasses import dataclass

@dataclass(frozen=True)
class LearningSettingsSnapshot:
    desired_retention: float
    initial_stability: float
    initial_difficulty: float
    promote_stability_multiplier: float
    promote_difficulty_delta: float
