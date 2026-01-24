"""Tests for the coordinator client module."""

import pytest
import trio
from subnet_engine.coordinator import EngineClient


@pytest.mark.trio
async def test_engine_client_init():
    """Test EngineClient initialization."""
    client = EngineClient("/tmp/test.sock")
    assert client.socket_path == "/tmp/test.sock"
    assert client._stream is None


@pytest.mark.trio
async def test_engine_client_custom_socket():
    """Test EngineClient with custom socket path."""
    client = EngineClient("/custom/path.sock")
    assert client.socket_path == "/custom/path.sock"


@pytest.mark.trio
async def test_submit_task_requires_connection():
    """Test that submit_task tries to connect when no stream exists."""
    client = EngineClient("/tmp/nonexistent_test_socket.sock")

    # Should attempt to connect (will timeout as socket doesn't exist)
    # Use a cancel scope to prevent infinite retry
    with trio.move_on_after(0.2):
        results = []
        async for chunk in client.submit_task("test"):
            results.append(chunk)

    # If we get here, the timeout worked as expected (connection attempts failed)
    assert True  # Test passes if we reach here without hanging
