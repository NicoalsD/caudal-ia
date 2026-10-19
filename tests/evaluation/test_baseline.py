import math

import pytest

from caudal_ia.evaluation.baseline import PersistenceForecaster, skill
from caudal_ia.forecasting.quantiles import P10_LEVEL, P50_LEVEL, P90_LEVEL

LEVELS = (P10_LEVEL, P50_LEVEL, P90_LEVEL)
PREDICTION_LENGTH = 3
# Context 10, 9, 9, 10, 12, 15 gives the changes -1, 0, 1, 2, 3 (five changes).
# With linear interpolation: Q(0.1) = -0.6 and Q(0.9) = 2.6. L = 15.
HAND_CONTEXT = (10.0, 9.0, 9.0, 10.0, 12.0, 15.0)
HAND_LAST = 15.0
HAND_P10 = 14.4
HAND_P90 = 17.6
FIVE_CHANGES = 5
FOUR_CHANGES = 4
SKILL_MODEL_MAE = 0.5
SKILL_PERSISTENCE_MAE = 1.0
SKILL_WORSE_MODEL_MAE = 2.0
EXPECTED_SKILL_BETTER = 0.5
EXPECTED_SKILL_WORSE = -1.0


def test_median_is_the_last_finite_value_even_with_a_trailing_gap() -> None:
    forecast = PersistenceForecaster().predict_quantiles(
        (10.0, 12.0, math.nan), PREDICTION_LENGTH, LEVELS
    )

    assert forecast.steps[0][1] == pytest.approx(12.0)


def test_band_uses_quantiles_of_the_daily_changes_by_hand() -> None:
    forecast = PersistenceForecaster().predict_quantiles(
        HAND_CONTEXT, PREDICTION_LENGTH, LEVELS
    )

    p10, p50, p90 = forecast.steps[0]
    assert p50 == pytest.approx(HAND_LAST)
    assert p10 == pytest.approx(HAND_P10)
    assert p90 == pytest.approx(HAND_P90)


def test_steady_rise_keeps_the_band_around_the_median() -> None:
    # Every daily change is +1, so L + Q(0.1) and L + Q(0.9) would both be above L.
    rising = (10.0, 11.0, 12.0, 13.0, 14.0, 15.0)

    forecast = PersistenceForecaster().predict_quantiles(
        rising, PREDICTION_LENGTH, LEVELS
    )

    p10, p50, p90 = forecast.steps[0]
    assert (p10, p50, p90) == (HAND_LAST, HAND_LAST, HAND_LAST + 1.0)


def test_every_step_repeats_the_same_band() -> None:
    forecast = PersistenceForecaster().predict_quantiles(
        HAND_CONTEXT, PREDICTION_LENGTH, LEVELS
    )

    assert len(forecast.steps) == PREDICTION_LENGTH
    assert len(set(forecast.steps)) == 1


def test_changes_across_a_gap_are_ignored() -> None:
    context = (10.0, 9.0, math.nan, 9.0, 10.0, 12.0, 15.0)

    forecast = PersistenceForecaster(min_changes=FOUR_CHANGES).predict_quantiles(
        context, PREDICTION_LENGTH, LEVELS
    )

    p10, p50, p90 = forecast.steps[0]
    assert p50 == pytest.approx(HAND_LAST)
    assert p10 < p50 < p90


def test_too_few_changes_gives_the_last_value_for_every_level() -> None:
    forecast = PersistenceForecaster(min_changes=FIVE_CHANGES + 1).predict_quantiles(
        HAND_CONTEXT, PREDICTION_LENGTH, LEVELS
    )

    assert forecast.steps[0] == (HAND_LAST, HAND_LAST, HAND_LAST)


def test_context_without_finite_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="no finite value"):
        PersistenceForecaster().predict_quantiles(
            (math.nan, math.nan), PREDICTION_LENGTH, LEVELS
        )


def test_reports_its_name_and_version() -> None:
    forecaster = PersistenceForecaster()

    assert (forecaster.name, forecaster.version) == ("naive-persistence", "1")


def test_skill_is_one_minus_the_mae_ratio() -> None:
    assert skill(SKILL_MODEL_MAE, SKILL_PERSISTENCE_MAE) == pytest.approx(
        EXPECTED_SKILL_BETTER
    )
    assert skill(SKILL_WORSE_MODEL_MAE, SKILL_PERSISTENCE_MAE) == pytest.approx(
        EXPECTED_SKILL_WORSE
    )


def test_skill_is_none_without_a_usable_baseline() -> None:
    assert skill(SKILL_MODEL_MAE, 0.0) is None
    assert skill(None, SKILL_PERSISTENCE_MAE) is None
    assert skill(SKILL_MODEL_MAE, None) is None
