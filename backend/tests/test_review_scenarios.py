from datetime import datetime, timezone

import pytest

from app.core.enums import ReviewRating
from app.domain.review.policy import ReviewPolicy
from app.domain.review.dto import LearningSettingsSnapshot
from app.domain.review.entities import CardLevelProgressState


def _fmt_td(td) -> str:
    minutes = td.total_seconds() / 60
    hours = minutes / 60
    days = hours / 24
    return f"{minutes:10.2f} min | {hours:8.2f} h | {days:8.4f} d"


def run_scenario(
    title: str,
    ratings: list[ReviewRating],
    *,
    initial_stability: float = 1.0,
    initial_difficulty: float = 5.0,
):
    policy = ReviewPolicy()
    settings = LearningSettingsSnapshot(
        desired_retention=0.90,
        initial_stability=initial_stability,
        initial_difficulty=initial_difficulty,
        promote_stability_multiplier=0.85,
        promote_difficulty_delta=0.5,
    )

    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    state = CardLevelProgressState(stability=initial_stability, difficulty=initial_difficulty)

    rows = []
    for i, rating in enumerate(ratings, start=1):
        updated = policy.apply_review(state=state, rating=rating, settings=settings, now=now)
        interval = updated.next_review - now

        rows.append(
            {
                "step": i,
                "rating": rating.value,
                "stability": updated.stability,
                "difficulty": updated.difficulty,
                "interval": interval,
                "next_review": updated.next_review,
            }
        )

        # симулируем, что следующий раз человек отвечает в момент scheduled review
        now = updated.next_review
        state = updated

    print("\n" + "=" * 90)
    print(title)
    print("-" * 90)
    print("step | rating | stability(days) | difficulty | interval (min|h|d)           | next_review")
    for r in rows:
        print(
            f"{r['step']:>4} | {r['rating']:<6} | {r['stability']:<14.6f} | {r['difficulty']:<10.4f} | "
            f"{_fmt_td(r['interval'])} | {r['next_review'].isoformat()}"
        )
    print("=" * 90)

    return rows


class TestHumanScenarios:
    def test_01_consistent_good_x10(self):
        rows = run_scenario("Scenario 01: consistent GOOD x10", [ReviewRating.good] * 10)
        intervals = [r["interval"] for r in rows]
        assert all(intervals[i] < intervals[i + 1] for i in range(len(intervals) - 1))

    def test_02_consistent_easy_x10_grows_faster_than_good(self):
        good_rows = run_scenario("Scenario 02A: GOOD x10", [ReviewRating.good] * 10)
        easy_rows = run_scenario("Scenario 02B: EASY x10", [ReviewRating.easy] * 10)
        assert easy_rows[-1]["interval"] > good_rows[-1]["interval"]

    def test_03_consistent_again_x10_crashes_interval(self):
        rows = run_scenario("Scenario 03: consistent AGAIN x10", [ReviewRating.again] * 10)
        # после нескольких AGAIN интервалы должны перестать быть большими
        assert rows[-1]["interval"] < rows[0]["interval"]

    def test_04_hard_x10_does_not_explode(self):
        rows = run_scenario("Scenario 04: consistent HARD x10", [ReviewRating.hard] * 10)
        # проверяем что next_review всегда в будущем относительно шага
        assert all(r["interval"].total_seconds() > 0 for r in rows)

    def test_05_good_good_good_then_again_drop(self):
        rows = run_scenario(
            "Scenario 05: GOOD,GOOD,GOOD, then AGAIN (drop)",
            [ReviewRating.good, ReviewRating.good, ReviewRating.good, ReviewRating.again],
        )
        assert rows[3]["interval"] < rows[2]["interval"]

    def test_06_recovery_after_again(self):
        rows = run_scenario(
            "Scenario 06: GOOD,GOOD, AGAIN, GOOD,GOOD (recovery)",
            [ReviewRating.good, ReviewRating.good, ReviewRating.again, ReviewRating.good, ReviewRating.good],
        )
        # после AGAIN упали, потом должны начать расти
        assert rows[2]["interval"] < rows[1]["interval"]
        assert rows[3]["interval"] > rows[2]["interval"]
        assert rows[4]["interval"] > rows[3]["interval"]

    def test_07_gradual_improvement_hard_to_easy(self):
        rows = run_scenario(
            "Scenario 07: HARD,HARD,GOOD,GOOD,EASY,EASY",
            [ReviewRating.hard, ReviewRating.hard, ReviewRating.good, ReviewRating.good, ReviewRating.easy, ReviewRating.easy],
        )
        assert rows[-1]["interval"] > rows[0]["interval"]

    def test_08_yoyo_easy_again_alternating(self):
        rows = run_scenario(
            "Scenario 08: EASY/AGAIN yo-yo",
            [ReviewRating.easy, ReviewRating.again] * 5,
        )
        # каждый AGAIN должен “просаживать” интервал относительно предыдущего EASY
        for i in range(1, len(rows), 2):
            assert rows[i]["interval"] < rows[i - 1]["interval"]

    def test_09_mixed_realistic(self):
        rows = run_scenario(
            "Scenario 09: mixed realistic",
            [
                ReviewRating.good, ReviewRating.good, ReviewRating.hard,
                ReviewRating.good, ReviewRating.easy, ReviewRating.good,
                ReviewRating.again, ReviewRating.hard, ReviewRating.good, ReviewRating.easy
            ],
        )
        assert len(rows) == 10
        assert all(r["interval"].total_seconds() > 0 for r in rows)

    def test_10_difficulty_is_clamped_1_to_10(self):
        rows_up = run_scenario("Scenario 10A: AGAIN x20 difficulty up clamp", [ReviewRating.again] * 20)
        assert all(1.0 <= r["difficulty"] <= 10.0 for r in rows_up)

        rows_down = run_scenario("Scenario 10B: EASY x40 difficulty down clamp", [ReviewRating.easy] * 40)
        assert all(1.0 <= r["difficulty"] <= 10.0 for r in rows_down)
