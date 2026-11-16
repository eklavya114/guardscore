"""Tests for the scoring math."""

import math

import pytest

from guardscore.scoring import (
    balanced_score,
    median_latency,
    p95_latency,
    percentile,
    rate,
    wilson_interval,
)


class TestRate:
    def test_simple_rate(self):
        assert rate(5, 10) == 0.5

    def test_zero_total_is_none(self):
        assert rate(0, 0) is None

    def test_zero_successes(self):
        assert rate(0, 10) == 0.0

    def test_all_successes(self):
        assert rate(10, 10) == 1.0


class TestWilsonInterval:
    def test_zero_total_is_none(self):
        assert wilson_interval(0, 0) is None

    def test_hand_computed_value(self):
        # 5 successes out of 6 trials, z = 1.96.
        # p = 0.8333, z2 = 3.8416
        # center = (0.8333 + 3.8416 / 12) / (1 + 3.8416 / 6)
        #        = (0.8333 + 0.32013) / (1.64027) = 0.70302
        # margin = 1.96 * sqrt((0.8333*0.1667 + 3.8416/24) / 6) / 1.64027
        # Computed independently below with plain arithmetic.
        p = 5 / 6
        z = 1.96
        z2 = z * z
        n = 6
        denom = 1 + z2 / n
        center = p + z2 / (2 * n)
        margin = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
        expected_low = (center - margin) / denom
        expected_high = (center + margin) / denom

        interval = wilson_interval(5, 6)
        assert interval is not None
        assert interval.low == pytest.approx(expected_low, abs=1e-9)
        assert interval.high == pytest.approx(expected_high, abs=1e-9)

    def test_interval_contains_point_estimate(self):
        interval = wilson_interval(8, 10)
        assert interval.low <= 0.8 <= interval.high

    def test_interval_bounds_are_within_zero_and_one(self):
        interval = wilson_interval(0, 5)
        assert 0.0 <= interval.low <= interval.high <= 1.0

        interval = wilson_interval(5, 5)
        assert 0.0 <= interval.low <= interval.high <= 1.0

    def test_no_division_by_zero_at_extremes(self):
        assert wilson_interval(0, 1) is not None
        assert wilson_interval(1, 1) is not None


class TestBalancedScore:
    def test_allow_all_scores_fifty_percent(self):
        # allow-all: catch rate 0, wrongly held rate 0
        score = balanced_score(catch_rate=0.0, wrongly_held_rate=0.0)
        assert score == 0.5

    def test_block_all_scores_fifty_percent(self):
        # block-all: catch rate 1, wrongly held rate 1
        score = balanced_score(catch_rate=1.0, wrongly_held_rate=1.0)
        assert score == 0.5

    def test_perfect_guard_scores_one(self):
        score = balanced_score(catch_rate=1.0, wrongly_held_rate=0.0)
        assert score == 1.0

    def test_worst_guard_scores_zero(self):
        score = balanced_score(catch_rate=0.0, wrongly_held_rate=1.0)
        assert score == 0.0

    def test_none_catch_rate_gives_none(self):
        assert balanced_score(catch_rate=None, wrongly_held_rate=0.0) is None

    def test_none_wrongly_held_rate_gives_none(self):
        assert balanced_score(catch_rate=1.0, wrongly_held_rate=None) is None


class TestPercentile:
    def test_empty_list_is_none(self):
        assert percentile([], 50) is None

    def test_median_of_odd_list(self):
        assert percentile([1, 2, 3], 50) == 2

    def test_median_of_single_value(self):
        assert percentile([42], 50) == 42

    def test_p95_nearest_rank(self):
        values = list(range(1, 21))  # 1..20
        # nearest rank for 95th percentile of 20 values: ceil(0.95 * 20) = 19
        assert percentile(values, 95) == 19

    def test_median_latency_helper(self):
        assert median_latency([10, 20, 30]) == 20

    def test_p95_latency_helper(self):
        assert p95_latency([10, 20, 30, 40]) == percentile([10, 20, 30, 40], 95)
