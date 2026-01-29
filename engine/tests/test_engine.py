"""Tests for the engine server module."""

import json
import pytest
from starlette.testclient import TestClient
from subnet_engine.engine import app


def test_jsonrpc_endpoint_invalid_request():
    """Test that invalid JSON-RPC requests return 400."""
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.post("/jsonrpc", data="invalid json")
    # Note: TestClient simulates 127.0.0.1 by default, but let's be safe.
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32700


def test_jsonrpc_endpoint_invalid_method():
    """Test that invalid methods return 404/Method not found."""
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.post(
        "/jsonrpc",
        json={"jsonrpc": "2.0", "method": "invalid_method", "params": {}, "id": 1},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == -32601


@pytest.mark.trio
async def test_jsonrpc_endpoint_success():
    """Test successful proxying to App via HTTP."""
    from httpx import AsyncClient, ASGITransport
    from unittest.mock import patch

    rpc_req = {
        "jsonrpc": "2.0",
        "method": "submit_task",
        "params": {"payload": "test"},
        "id": "test-1",
    }

    # Define mock App response (lines)
    app_response_lines = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "result": {"type": "chunk", "data": "hel"},
                "id": "test-1",
            }
        )
        + "\n",
        json.dumps({"jsonrpc": "2.0", "result": {"type": "done"}, "id": "test-1"})
        + "\n",
    ]

    class MockResponse:
        def __init__(self):
            self.status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_lines(self):
            for line in app_response_lines:
                yield line

    def mock_stream_func(*args, **kwargs):
        return MockResponse()

    with patch("httpx.AsyncClient.stream", side_effect=mock_stream_func):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1"
        ) as ac:
            response = await ac.post("/jsonrpc", json=rpc_req)
            assert response.status_code == 200

            lines = []
            async for line in response.aiter_lines():
                if line:
                    lines.append(line)

            assert len(lines) == 2
            assert "chunk" in lines[0]
            assert "done" in lines[1]
