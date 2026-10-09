from __future__ import annotations

from typing import ClassVar

from caudal_ia.model_catalog import CHRONOS_MODEL_SPECS, ModelSpec


class DuplicateModelError(Exception):
    """Raised when a model name is already registered."""


class UnknownModelError(Exception):
    """Raised when a requested model name is not registered."""


class ModelRegistry:
    """Keep available model specifications in one shared registry.

    @pattern P01 Singleton
    """

    _instance: ClassVar[ModelRegistry | None] = None

    def __init__(self) -> None:
        self._specs: dict[str, ModelSpec] = {}
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
