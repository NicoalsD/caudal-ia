import pytest

from caudal_ia.config import Settings
from caudal_ia.request_validation import (
    MIN_PREDICTION_LENGTH,
    PREDICTION_LENGTH_FIELD,
    PREDICTION_LENGTH_OUT_OF_RANGE,
    QUANTILE_LEVELS_FIELD,
    QUANTILE_LEVELS_NOT_SUPPORTED,
    SUPPORTED_QUANTILE_LEVELS,
    ContractValidationError,
    validate_prediction_length,
    validate_quantile_levels,
)

TEST_MAX_PREDICTION_LENGTH = 30
BELOW_MINIMUM_PREDICTION_LENGTH = 0
ABOVE_MAXIMUM_INCREMENT = 1
UNSUPPORTED_QUANTILE_LEVELS = ([0.1, 0.9], [0.1, 0.9, 0.5])


def test_minimum_prediction_length_passes() -> None:
    validate_prediction_length(
        MIN_PREDICTION_LENGTH,
        Settings(max_prediction_length=TEST_MAX_PREDICTION_LENGTH),
    )


def test_maximum_prediction_length_passes() -> None:
    validate_prediction_length(
        TEST_MAX_PREDICTION_LENGTH,
        Settings(max_prediction_length=TEST_MAX_PREDICTION_LENGTH),
    )


@pytest.mark.parametrize(
    "prediction_length",
    [
        BELOW_MINIMUM_PREDICTION_LENGTH,
        TEST_MAX_PREDICTION_LENGTH + ABOVE_MAXIMUM_INCREMENT,
    ],
)
def test_prediction_length_out_of_range_is_rejected(
    prediction_length: int,
) -> None:
    with pytest.raises(ContractValidationError) as error:
        validate_prediction_length(
            prediction_length,
            Settings(max_prediction_length=TEST_MAX_PREDICTION_LENGTH),
        )

    assert error.value.reason == PREDICTION_LENGTH_OUT_OF_RANGE
    assert error.value.field == PREDICTION_LENGTH_FIELD


@pytest.mark.parametrize("quantile_levels", UNSUPPORTED_QUANTILE_LEVELS)
def test_unsupported_quantile_levels_are_rejected(
    quantile_levels: list[float],
) -> None:
    with pytest.raises(ContractValidationError) as error:
        validate_quantile_levels(quantile_levels)

    assert error.value.reason == QUANTILE_LEVELS_NOT_SUPPORTED
    assert error.value.field == QUANTILE_LEVELS_FIELD


def test_supported_quantile_levels_pass() -> None:
    validate_quantile_levels(list(SUPPORTED_QUANTILE_LEVELS))
