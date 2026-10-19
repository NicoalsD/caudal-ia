from __future__ import annotations

import threading
from typing import ClassVar

from caudal_ia.config import Settings
from caudal_ia.forecasting.creator import ForecasterCreator
from caudal_ia.forecasting.forecaster import Forecaster
from caudal_ia.model_catalog import CHRONOS_MODEL_SPECS, ModelSpec


class DuplicateModelError(Exception):
    """Raised when a model name is already registered."""


class UnknownModelError(Exception):
    """Raised when a requested model name is not registered."""


class ModelNotLoadedError(Exception):
    """Raised when a registered model has not been loaded yet."""


class ModelRegistry:
    """Keep available model specifications in one shared registry.

    @pattern P01 Singleton
    """

    _instance: ClassVar[ModelRegistry | None] = None

    def __init__(self) -> None:
        self._specs: dict[str, ModelSpec] = {}
        self._forecasters: dict[str, Forecaster] = {}
        self._load_lock = threading.Lock()
        for spec in CHRONOS_MODEL_SPECS:
            self.register(spec)

    @classmethod
    def get_instance(cls) -> ModelRegistry:
        """Return the shared registry, creating it on first access."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the shared instance for use by tests only."""
        cls._instance = None

    def register(self, spec: ModelSpec) -> None:
        """Register a model specification unless its name is already used."""
        if spec.name in self._specs:
            raise DuplicateModelError(f"El modelo '{spec.name}' ya está registrado.")
        self._specs[spec.name] = spec

    def get_spec(self, name: str) -> ModelSpec:
        """Return the specification for a registered model name."""
        try:
            return self._specs[name]
        except KeyError as error:
            raise UnknownModelError(
                f"No existe un modelo registrado con el nombre '{name}'."
            ) from error

    def list_specs(self) -> tuple[ModelSpec, ...]:
        """Return registered specifications in registration order."""
        return tuple(self._specs.values())

    def load(
        self,
        spec: ModelSpec,
        creator: ForecasterCreator,
        settings: Settings,
    ) -> Forecaster:
        """Load the forecaster of ``spec`` once and keep it in memory."""
        with self._load_lock:
            if spec.name not in self._forecasters:
                self._forecasters[spec.name] = creator.create(spec, settings)
            return self._forecasters[spec.name]

    def get_forecaster(self, name: str) -> Forecaster:
        """Return the loaded forecaster for a model name."""
        try:
            return self._forecasters[name]
        except KeyError as error:
            raise ModelNotLoadedError(
                f"El modelo '{name}' todavía no está cargado."
            ) from error


def resolve_active_model(settings: Settings) -> ModelSpec:
    """Resolve the configured model, failing if it is not registered."""
    return ModelRegistry.get_instance().get_spec(settings.chronos_model_id)
