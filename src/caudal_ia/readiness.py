import threading


class ModelReadiness:
    """Track whether the active model finished loading, successfully or not."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._is_loaded = False
        self._settled = threading.Event()

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def mark_loaded(self) -> None:
        self._is_loaded = True
        self._settled.set()

    def mark_failed(self) -> None:
        self._is_loaded = False
        self._settled.set()

    def wait(self, timeout_seconds: float) -> bool:
        """Block until loading ends; return whether the model is loaded."""
        self._settled.wait(timeout_seconds)
        return self._is_loaded
