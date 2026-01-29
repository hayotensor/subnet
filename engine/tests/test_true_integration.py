import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from subnet_engine.coordinator import EngineClient
from subnet_engine.engine import app as engine_app
from subnet_app.server import app as app_app


@pytest.mark.trio
async def test_end_to_end_http_flow():
    """
    True integration test: EngineClient -> Engine -> App
    Links both Starlette apps via ASGITransport to avoid real network overhead
    while testing the actual handler logic.
    """

    # We need to ensure that the httpx.AsyncClient INSIDE engine_app.proxy_generator
    # uses a transport that points to app_app.
    # The Engine calls APP_URL (e.g. http://127.0.0.1:5001/jsonrpc).

    # We patch httpx.AsyncClient at the module level in subnet_engine.engine
    # so that it uses our ASGITransport(app=app_app).

    def internal_client_mock(*args, **kwargs):
        # Force it to use the app_app transport for any internal calls
        kwargs["transport"] = ASGITransport(app=app_app)
        # We must also ensure it handles base_url correctly if needed,
        # but ASGITransport handles any request to any host if passed in app.
        return AsyncClient(*args, **kwargs)

    # We also need to ensure the Coordinator uses a transport pointing to engine_app
    with patch("httpx.AsyncClient", side_effect=internal_client_mock):
        # Now we create the Coordinator's client.
        # But wait, EngineClient also creates its own AsyncClient.
        # Our side_effect patch will handle BOTH EngineClient AND the Engine internal proxy.

        # We need a way to distinguish:
        # call1: Coordinator -> engine_app
        # call2: engine_app -> app_app

        def universal_client_factory(*args, **kwargs):
            url = kwargs.get("base_url") or (args[0] if args else "")
            # If the URL is engine, point to engine_app
            if "5000" in str(url) or "engine" in str(url):
                kwargs["transport"] = ASGITransport(app=engine_app)
            # If the URL is app, point to app_app
            else:
                kwargs["transport"] = ASGITransport(app=app_app)
            return AsyncClient(*args, **kwargs)

        with patch("httpx.AsyncClient", side_effect=universal_client_factory):
            with patch(
                "uuid.uuid4", return_value=MagicMock(__str__=lambda x: "integration-id")
            ):
                client = EngineClient(host="engine", port=5000)

                payload = "integration test payload"
                results = []
                async for chunk in client.submit_task(payload):
                    results.append(chunk)

                assert len(results) > 0
                full_text = "".join(results)
                # The real MockLLM yields: "This ", "is ", "a ", "generated ", "response ", "from ", self.model_name
                assert "This is a generated response from gpt2" in full_text
                assert results[0] == "This "


@pytest.mark.trio
async def test_invalid_method_error_propagation():
    """Test that calling a valid engine endpoint with an invalid method returns a 404/JSON-RPC error."""
    # We bypass the client for this one to test the proxy server error handling directly
    transport = ASGITransport(app=engine_app)
    async with AsyncClient(transport=transport, base_url="http://engine") as client:
        bad_req = {
            "jsonrpc": "2.0",
            "method": "non_existent_method",
            "params": {},
            "id": 1,
        }
        response = await client.post("/jsonrpc", json=bad_req)
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == -32601
        assert "Method not found" in data["error"]["message"]


@pytest.mark.trio
async def test_app_offline_error_propagation():
    """Test how Engine handles it when the downstream App is entirely failing."""

    class MockFailingResponse:
        def __init__(self):
            self.status_code = 500

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aread(self):
            return b"Internal Server Error"

    def failing_client_mock(*args, **kwargs):
        # We need a regular function that returns an ACM

        c = AsyncClient(*args, **kwargs)
        c.stream = MagicMock(return_value=MockFailingResponse())
        return c

    with patch("httpx.AsyncClient", side_effect=failing_client_mock):
        transport = ASGITransport(app=engine_app)
        async with AsyncClient(transport=transport, base_url="http://engine") as client:
            req = {
                "jsonrpc": "2.0",
                "method": "submit_task",
                "params": {"payload": "test"},
                "id": 1,
            }
            # The engine returns a StreamingResponse. We need to check the lines in it.
            async with client.stream("POST", "/jsonrpc", json=req) as resp:
                lines = [line async for line in resp.aiter_lines()]
                assert len(lines) == 1
                error_data = json.loads(lines[0])
                assert (
                    "App Error: Internal Server Error" in error_data["error"]["message"]
                )
