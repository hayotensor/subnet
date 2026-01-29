"""Integration tests for the complete HTTP engine-coordinator system."""

import json
import pytest
import trio
import uvicorn
from subnet_engine.coordinator import EngineClient
from subnet_engine.engine import app as engine_fastapi


class BackgroundServer:
    def __init__(self, app, host="127.0.0.1", port=0):
        self.app = app
        self.host = host
        self.port = port
        self._server = None

    async def run(self, task_status=trio.TASK_STATUS_IGNORED):
        config = uvicorn.Config(
            self.app, host=self.host, port=self.port, log_level="error"
        )
        self._server = uvicorn.Server(config)

        # We need to reach into uvicorn to get the actual port if it was 0
        # This is a bit tricky with trio.
        task_status.started()
        await self._server.serve()


@pytest.mark.trio
async def test_full_communication_flow():
    """Test complete communication between engine and coordinator via HTTP."""
    # Note: Running actual uvicorn servers in trio tests is heavy.
    # A better approach for unit-integration is using httpx.ASGITransport
    # to link the clients directly to the apps without real sockets.

    from httpx import AsyncClient, ASGITransport

    # End-to-end mock: Coordinator -> Engine -> App
    # We can mock the Engine's HTTP call to the App.

    # Let's mock 'httpx.AsyncClient.stream' globally like in test_engine.py
    # to simulate the Engine calling the App.

    rpc_req_payload = "hello world integration"
    app_response_lines = [
        json.dumps(
            {"jsonrpc": "2.0", "result": {"type": "chunk", "data": "hello"}, "id": "1"}
        ),
        json.dumps(
            {"jsonrpc": "2.0", "result": {"type": "chunk", "data": "world"}, "id": "1"}
        ),
        json.dumps({"jsonrpc": "2.0", "result": {"type": "done"}, "id": "1"}),
    ]

    class MockAppResponse:
        def __init__(self):
            self.status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_lines(self):
            for line in app_response_lines:
                yield line

    def mock_app_stream(*args, **kwargs):
        return MockAppResponse()

    from unittest.mock import patch, MagicMock

    with patch("httpx.AsyncClient.stream", side_effect=mock_app_stream):
        with patch("uuid.uuid4", return_value=MagicMock(__str__=lambda x: "1")):
            # Coordinator calls Engine
            # We use ASGITransport to point Coordinator to Engine app directly

            async with AsyncClient(
                transport=ASGITransport(app=engine_fastapi), base_url="http://engine"
            ):
                # We need to inject this client or base URL into EngineClient?
                # Actually EngineClient uses DEFAULT_HOST/PORT.
                # Let's just mock the EngineClient's network call too or point it to a real server.

                # For a true integration test WITHOUT real sockets, we can't easily use EngineClient
                # as is because it creates its own httpx.AsyncClient internally.

                # Let's patch EngineClient.url to point to our mock engine
                client = EngineClient(host="engine", port=80)

                # We must also ensure EngineClient uses our transport-aware AsyncClient.
                # Since EngineClient creates its own in 'async with httpx.AsyncClient(...)',
                # we should patch httpx.AsyncClient constructor.

                def mock_client_factory(*args, **kwargs):
                    # Ensure it uses our transport for the 'engine' host
                    kwargs["transport"] = ASGITransport(app=engine_fastapi)
                    return AsyncClient(*args, **kwargs)

                with patch("httpx.AsyncClient", side_effect=mock_client_factory):
                    results = []
                    async for chunk in client.submit_task(rpc_req_payload):
                        results.append(chunk)

                    assert results == ["hello", "world"]


@pytest.mark.trio
async def test_error_propagation_integration():
    """Test that errors from App propagate correctly through Engine to Coordinator."""
    from httpx import AsyncClient, ASGITransport
    from unittest.mock import patch, MagicMock

    class MockErrorResponse:
        def __init__(self):
            self.status_code = 200  # JSON-RPC errors often 200 but contain error object

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_lines(self):
            yield json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": "Simulated App Failure"},
                    "id": "1",
                }
            )

    with patch("httpx.AsyncClient.stream", return_value=MockErrorResponse()):
        with patch("uuid.uuid4", return_value=MagicMock(__str__=lambda x: "1")):
            client = EngineClient(host="engine", port=80)

            def mock_client_factory(*args, **kwargs):
                kwargs["transport"] = ASGITransport(app=engine_fastapi)
                return AsyncClient(*args, **kwargs)

            with patch("httpx.AsyncClient", side_effect=mock_client_factory):
                results = []
                async for chunk in client.submit_task("test"):
                    results.append(chunk)

                assert (
                    len(results) == 0
                )  # Should have failed and logged, not yielded chunks
