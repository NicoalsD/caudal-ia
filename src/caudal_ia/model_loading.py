import logging
import threading

from caudal_ia.config import Settings
from caudal_ia.forecasting.creator import ForecasterCreator
from caudal_ia.model_catalog import ModelSpec
from caudal_ia.model_registry import ModelRegistry
from caudal_ia.readiness import ModelReadiness

logger = logging.getLogger(__name__)
LOADER_THREAD_NAME = "model-loader"


def load_active_model(
    spec: ModelSpec,
    creator: ForecasterCreator,
    settings: Settings,
    readiness: ModelReadiness,
) -> None:
    """Load the active model into the registry and report the outcome."""
    try:
        ModelRegistry.get_instance().load(spec, creator, settings)
    except Exception:
        logger.exception("Model load failed model=%s", spec.name)
        readiness.mark_failed()
        return
    readiness.mark_loaded()


def start_model_loading(
    spec: ModelSpec,
    creator: ForecasterCreator,
    settings: Settings,
    readiness: ModelReadiness,
) -> threading.Thread:
    """Load the model in the background so /v1/health answers right away."""
    thread = threading.Thread(
        target=load_active_model,
        args=(spec, creator, settings, readiness),
        name=LOADER_THREAD_NAME,
        daemon=True,
    )
    thread.start()
    return thread
