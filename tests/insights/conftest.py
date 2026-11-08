from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient

from caudal_ia.main import app
from tests.fakes import FakeLlmClient


@pytest.fixture
def use_llm(
    client: TestClient,
) -> Generator[Callable[[FakeLlmClient | None], None], None, None]:
    """Install a fake LLM (or none) on the app for the duration of a test."""

    def install(llm: FakeLlmClient | None) -> None:
        app.state.llm_client = llm

    yield install
    if hasattr(app.state, "llm_client"):
        del app.state.llm_client
