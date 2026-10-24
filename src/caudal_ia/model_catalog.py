from dataclasses import dataclass
from importlib.metadata import version

MAX_PREDICTION_LENGTH = 30
# Hugging Face models carry no version of their own; the weights are tied to the
# chronos-forecasting release that loads them.
CHRONOS_PACKAGE_VERSION = version("chronos-forecasting")
CHRONOS_QUANTILE_LEVELS = (0.1, 0.5, 0.9)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    version: str
    parameters_millions: int
    quantile_levels: tuple[float, ...]
    max_prediction_length: int


CHRONOS_MODEL_SPECS = [
    ModelSpec(
        name="autogluon/chronos-2-small",
        version=CHRONOS_PACKAGE_VERSION,
        parameters_millions=28,
        quantile_levels=CHRONOS_QUANTILE_LEVELS,
        max_prediction_length=MAX_PREDICTION_LENGTH,
    ),
    ModelSpec(
        name="amazon/chronos-bolt-small",
        version=CHRONOS_PACKAGE_VERSION,
        parameters_millions=48,
        quantile_levels=CHRONOS_QUANTILE_LEVELS,
        max_prediction_length=MAX_PREDICTION_LENGTH,
    ),
    # Smallest model: it fits the 512 MB of a free hosting instance.
    ModelSpec(
        name="amazon/chronos-bolt-tiny",
        version=CHRONOS_PACKAGE_VERSION,
        parameters_millions=9,
        quantile_levels=CHRONOS_QUANTILE_LEVELS,
        max_prediction_length=MAX_PREDICTION_LENGTH,
    ),
]
