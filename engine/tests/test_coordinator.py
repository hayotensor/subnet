"""Tests for the coordinator client module."""

import json
import pytest
from unittest.mock import patch, MagicMock
from subnet_engine.coordinator import EngineClient


@pytest.mark.trio
async def test_engine_client_init():
    """Test EngineClient initialization."""
    client = EngineClient(host="127.0.0.1", port=5000)
    assert client.host == "127.0.0.1"
    assert client.port == 5000
    assert "http://127.0.0.1:5000/jsonrpc" == client.url


@pytest.mark.trio
async def test_submit_task_success():
    """Test successful task submission via HTTP."""
    client = EngineClient(host="127.0.0.1", port=5000)

    # Define mock response lines
    response_lines = [
        json.dumps(
            {"jsonrpc": "2.0", "result": {"type": "chunk", "data": "hel"}, "id": "123"}
        ),
        json.dumps({"jsonrpc": "2.0", "result": {"type": "done"}, "id": "123"}),
    ]

    class MockResponse:
        def __init__(self):
            self.status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_lines(self):
            for line in response_lines:
                yield line

        async def aread(self):
            return b""

    # stream() returns a CM, so mock it with a regular function returning MockResponse
    def mock_stream_func(*args, **kwargs):
        return MockResponse()

    with patch("httpx.AsyncClient.stream", side_effect=mock_stream_func):
        with patch(
            "uuid.uuid4",
            return_value=MagicMock(
                hex="b228faee-85f6-4292-9d8b-aa8b60260168", __str__=lambda x: "123"
            ),
        ):
            results = []
            async for chunk in client.submit_task("test payload"):
                results.append(chunk)

            assert len(results) == 1
            assert results[0] == "hel"


@pytest.mark.trio
async def test_submit_task_http_error():
    """Test handling of HTTP errors in submit_task."""
    client = EngineClient(host="127.0.0.1", port=5000)

    class MockErrorResponse:
        def __init__(self):
            self.status_code = 500

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aread(self):
            return b"Internal Server Error"

    def mock_error_func(*args, **kwargs):
        return MockErrorResponse()

    with patch("httpx.AsyncClient.stream", side_effect=mock_error_func):
        # Should return without yielding (logs the error)
        results = []
        async for chunk in client.submit_task("test"):
            results.append(chunk)

        assert len(results) == 0
