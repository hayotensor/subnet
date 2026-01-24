"""Pytest fixtures and test utilities for subnet-engine tests."""

import tempfile
from pathlib import Path

import pytest
import trio


@pytest.fixture
def temp_socket_path():
    """Provide a temporary socket path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = Path(tmpdir) / "test_engine.sock"
        yield str(socket_path)
        # Cleanup happens automatically when context exits
        if socket_path.exists():
            socket_path.unlink()


@pytest.fixture
def mock_stream():
    """Create a mock stream for testing message sending/receiving."""

    class MockStream:
        def __init__(self):
            self.sent_data = bytearray()
            self.recv_data = bytearray()
            self.recv_position = 0
            self.is_closed = False

        async def send_all(self, data):
            if self.is_closed:
                raise trio.ClosedResourceError
            self.sent_data.extend(data)

        async def receive_some(self, max_bytes):
            if self.is_closed:
                raise trio.ClosedResourceError
            if self.recv_position >= len(self.recv_data):
                return b""
            chunk = self.recv_data[self.recv_position : self.recv_position + max_bytes]
            self.recv_position += len(chunk)
            return bytes(chunk)

        def set_recv_data(self, data):
            """Set data to be returned by receive_some."""
            self.recv_data = bytearray(data)
            self.recv_position = 0

        def get_sent_data(self):
            """Get all data that was sent."""
            return bytes(self.sent_data)

        def close(self):
            """Mark stream as closed."""
            self.is_closed = True

    return MockStream()
