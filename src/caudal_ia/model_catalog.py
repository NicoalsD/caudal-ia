from dataclasses import dataclass

MAX_PREDICTION_LENGTH = 30
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
        version="2.0.0",
        parameters_millions=28,
        quantile_levels=CHRONOS_QUANTILE_LEVELS,
        max_prediction_length=MAX_PREDICTION_LENGTH,
    ),
    ModelSpec(
        name="amazon/chronos-bolt-small",
        version="por-verificar",  # Version not confirmed in the documentation.
        parameters_millions=48,
        quantile_levels=CHRONOS_QUANTILE_LEVELS,
        max_prediction_length=MAX_PREDICTION_LENGTH,
    ),
]
