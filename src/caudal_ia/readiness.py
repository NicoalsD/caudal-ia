DEFAULT_MODEL_NAME = "autogluon/chronos-2-small"


class ModelReadiness:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def mark_loaded(self) -> None:
        self._is_loaded = True
