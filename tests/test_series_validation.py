from datetime import UTC, datetime, timedelta

import pytest

from caudal_ia.config import Settings
from caudal_ia.series_validation import (
    LENGTH_MISMATCH,
    NOT_FINITE_VALUE,
    TIMESTAMP_PARSE_ERROR,
    TIMESTAMPS_NOT_INCREASING,
    TOO_MANY_POINTS,
    SeriesValidationError,
    validate_series,
)

TEST_FORECAST_MIN_POINTS = 7
TEST_MAX_SERIES_POINTS = 2000
ONE_ADDITIONAL_POINT = 1
ONE_FEWER_POINT = 1
PREVIOUS_TIMESTAMP_INDEX = 1
START_YEAR = 2026
START_MONTH = 10
START_DAY = 1
INVALID_TIMESTAMP_INDEX = 2
NON_INCREASING_TIMESTAMP_INDEX = 2
NON_FINITE_VALUE_INDEX = 1
NAN_VALUE = float("nan")
INFINITE_VALUE = float("inf")
NEGATIVE_INFINITE_VALUE = -float("inf")
TIMEZONELESS_TIMESTAMP = "2026-10-03T00:00:00"


def make_settings() -> Settings:
    return Settings(
        forecast_min_points=TEST_FORECAST_MIN_POINTS,
        max_series_points=TEST_MAX_SERIES_POINTS,
    )


def make_timestamps(point_count: int) -> list[str]:
    start = datetime(START_YEAR, START_MONTH, START_DAY, tzinfo=UTC)
    return [(start + timedelta(days=index)).isoformat() for index in range(point_count)]


def test_valid_series_passes() -> None:
    validate_series(
        make_timestamps(TEST_FORECAST_MIN_POINTS),
        [float(index) for index in range(TEST_FORECAST_MIN_POINTS)],
        make_settings(),
    )


def test_length_mismatch_reports_no_index() -> None:
    with pytest.raises(SeriesValidationError) as error:
        validate_series(make_timestamps(TEST_FORECAST_MIN_POINTS), [], make_settings())

    assert error.value.reason == LENGTH_MISMATCH
    assert error.value.index is None
    assert "longitud" in str(error.value)


def test_too_many_points_is_rejected() -> None:
    point_count = TEST_MAX_SERIES_POINTS + ONE_ADDITIONAL_POINT

    with pytest.raises(SeriesValidationError) as error:
        validate_series(
            make_timestamps(point_count),
            [float(index) for index in range(point_count)],
            make_settings(),
        )

    assert error.value.reason == TOO_MANY_POINTS
    assert error.value.index == TEST_MAX_SERIES_POINTS


def test_invalid_timestamp_reports_first_failing_index() -> None:
    timestamps = make_timestamps(TEST_FORECAST_MIN_POINTS)
    timestamps[INVALID_TIMESTAMP_INDEX] = "not-a-timestamp"

    with pytest.raises(SeriesValidationError) as error:
        validate_series(
            timestamps,
            [float(index) for index in range(TEST_FORECAST_MIN_POINTS)],
            make_settings(),
        )

    assert error.value.reason == TIMESTAMP_PARSE_ERROR
    assert error.value.index == INVALID_TIMESTAMP_INDEX


def test_timestamp_without_timezone_is_rejected() -> None:
    timestamps = make_timestamps(TEST_FORECAST_MIN_POINTS)
    timestamps[INVALID_TIMESTAMP_INDEX] = TIMEZONELESS_TIMESTAMP

    with pytest.raises(SeriesValidationError) as error:
        validate_series(
            timestamps,
            [float(index) for index in range(TEST_FORECAST_MIN_POINTS)],
            make_settings(),
        )

    assert error.value.reason == TIMESTAMP_PARSE_ERROR
    assert error.value.index == INVALID_TIMESTAMP_INDEX


def test_non_increasing_timestamp_reports_first_failing_index() -> None:
    timestamps = make_timestamps(TEST_FORECAST_MIN_POINTS)
    timestamps[NON_INCREASING_TIMESTAMP_INDEX] = timestamps[PREVIOUS_TIMESTAMP_INDEX]

    with pytest.raises(SeriesValidationError) as error:
        validate_series(
            timestamps,
            [float(index) for index in range(TEST_FORECAST_MIN_POINTS)],
            make_settings(),
        )

    assert error.value.reason == TIMESTAMPS_NOT_INCREASING
    assert error.value.index == NON_INCREASING_TIMESTAMP_INDEX


@pytest.mark.parametrize(
    "non_finite_value",
    [NAN_VALUE, INFINITE_VALUE, NEGATIVE_INFINITE_VALUE],
)
def test_non_finite_values_are_rejected(non_finite_value: float) -> None:
    values = [float(index) for index in range(TEST_FORECAST_MIN_POINTS)]
    values[NON_FINITE_VALUE_INDEX] = non_finite_value

    with pytest.raises(SeriesValidationError) as error:
        validate_series(
            make_timestamps(TEST_FORECAST_MIN_POINTS), values, make_settings()
        )

    assert error.value.reason == NOT_FINITE_VALUE
    assert error.value.index == NON_FINITE_VALUE_INDEX


def test_maximum_allowed_series_length_passes() -> None:
    validate_series(
        make_timestamps(TEST_MAX_SERIES_POINTS),
        [float(index) for index in range(TEST_MAX_SERIES_POINTS)],
        make_settings(),
    )
