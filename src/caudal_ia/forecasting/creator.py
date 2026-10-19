import logging
from abc import ABC, abstractmethod

from chronos import BaseChronosPipeline

from caudal_ia.config import Settings
from caudal_ia.forecasting.chronos_adapter import ChronosForecasterAdapter
from caudal_ia.forecasting.decorators import TimingForecaster
from caudal_ia.forecasting.forecaster import Forecaster
from caudal_ia.model_catalog import ModelSpec

logger = logging.getLogger(__name__)


class ForecasterCreator(ABC):
    """Build the forecaster for a registered model.

    Subclasses decide which concrete ``Forecaster`` to build; ``create`` keeps the
    steps every creator shares.

    @pattern P02 Factory Method
    """

    def create(self, spec: ModelSpec, settings: Settings) -> Forecaster:
        logger.info("Loading forecaster model=%s", spec.name)
        forecaster: Forecaster = TimingForecaster(
            self.create_forecaster(spec, settings)
        )
        logger.info("Forecaster ready model=%s", forecaster.name)
        return forecaster

    @abstractmethod
    def create_forecaster(self, spec: ModelSpec, settings: Settings) -> Forecaster:
        """Return a ready-to-use forecaster for ``spec``."""


class ChronosForecasterCreator(ForecasterCreator):
    """Load Chronos-2 or Chronos-Bolt weights from Hugging Face on the CPU."""

    def create_forecaster(self, spec: ModelSpec, settings: Settings) -> Forecaster:
        pipeline = BaseChronosPipeline.from_pretrained(
            spec.name,
            device_map=settings.chronos_device,
        )
        return ChronosForecasterAdapter(pipeline, spec.name, spec.version)
