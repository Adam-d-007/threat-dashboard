"""No test reaches the network: a fetch that was not replaced fails loudly."""

import httpx
import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError(f"a test tried to reach the network: {args[:2]}")
    for name in ("get", "post", "request"):
        monkeypatch.setattr(httpx, name, refuse)
