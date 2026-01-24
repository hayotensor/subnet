"""Tests for the engine server module."""

import struct

import msgpack
import pytest
from subnet_engine.engine import handle_task, open_unix_listener


@pytest.mark.trio
async def test_handle_task_basic(mock_stream):
    """Test basic task handling."""
    req = {"request_id": "test-123", "payload": "hello world test"}

    await handle_task(mock_stream, req)

    # Parse all messages sent
    sent_data = mock_stream.get_sent_data()
    messages = []
    pos = 0
    while pos < len(sent_data):
        length = struct.unpack("!I", sent_data[pos : pos + 4])[0]
        payload = sent_data[pos + 4 : pos + 4 + length]
        messages.append(msgpack.unpackb(payload, raw=False))
        pos += 4 + length

    # Should have 4 messages: 3 chunks + 1 done
    assert len(messages) == 4

    # Check chunk messages
    assert messages[0]["type"] == "chunk"
    assert messages[0]["data"] == "hello"
    assert messages[1]["type"] == "chunk"
    assert messages[1]["data"] == "world"
    assert messages[2]["type"] == "chunk"
    assert messages[2]["data"] == "test"

    # Check done message
    assert messages[3]["type"] == "done"
    assert messages[3]["request_id"] == "test-123"


@pytest.mark.trio
async def test_handle_task_empty_payload(mock_stream):
    """Test handling task with empty payload."""
    req = {"request_id": "empty-test", "payload": ""}

    await handle_task(mock_stream, req)

    sent_data = mock_stream.get_sent_data()
    # Parse messages
    messages = []
    pos = 0
    while pos < len(sent_data):
        length = struct.unpack("!I", sent_data[pos : pos + 4])[0]
        payload = sent_data[pos + 4 : pos + 4 + length]
        messages.append(msgpack.unpackb(payload, raw=False))
        pos += 4 + length

    # Should only have done message (no chunks from empty payload)
    assert len(messages) == 1
    assert messages[0]["type"] == "done"
    assert messages[0]["request_id"] == "empty-test"


@pytest.mark.trio
async def test_handle_task_single_word(mock_stream):
    """Test handling task with single word payload."""
    req = {"request_id": "single", "payload": "word"}

    await handle_task(mock_stream, req)

    sent_data = mock_stream.get_sent_data()
    messages = []
    pos = 0
    while pos < len(sent_data):
        length = struct.unpack("!I", sent_data[pos : pos + 4])[0]
        payload = sent_data[pos + 4 : pos + 4 + length]
        messages.append(msgpack.unpackb(payload, raw=False))
        pos += 4 + length

    # 1 chunk + 1 done
    assert len(messages) == 2
    assert messages[0]["type"] == "chunk"
    assert messages[0]["data"] == "word"
    assert messages[1]["type"] == "done"


@pytest.mark.trio
async def test_handle_task_missing_request_id(mock_stream):
    """Test that tasks without request_id are ignored."""
    req = {"payload": "test"}

    await handle_task(mock_stream, req)

    # Should send nothing if no request_id
    sent_data = mock_stream.get_sent_data()
    assert len(sent_data) == 0


@pytest.mark.trio
async def test_handle_task_missing_payload(mock_stream):
    """Test handling task with missing payload (defaults to empty string)."""
    req = {"request_id": "no-payload"}

    await handle_task(mock_stream, req)

    sent_data = mock_stream.get_sent_data()
    messages = []
    pos = 0
    while pos < len(sent_data):
        length = struct.unpack("!I", sent_data[pos : pos + 4])[0]
        payload = sent_data[pos + 4 : pos + 4 + length]
        messages.append(msgpack.unpackb(payload, raw=False))
        pos += 4 + length

    # Should only have done message
    assert len(messages) == 1
    assert messages[0]["type"] == "done"


@pytest.mark.trio
async def test_handle_task_send_error(mock_stream):
    """Test handling when sending fails."""

    class FailingStream:
        async def send_all(self, data):
            raise Exception("Send failed")

    req = {"request_id": "error-test", "payload": "test"}
    stream = FailingStream()

    # Should not raise, just log the error
    await handle_task(stream, req)


@pytest.mark.trio
async def test_open_unix_listener(temp_socket_path):
    """Test creating a Unix socket listener."""
    listeners = await open_unix_listener(temp_socket_path)

    assert len(listeners) == 1
    assert listeners[0] is not None

    # Clean up
    listeners[0].socket.close()


@pytest.mark.trio
async def test_handle_task_preserves_request_id(mock_stream):
    """Test that all responses include the correct request_id."""
    req = {"request_id": "preserve-test", "payload": "one two"}

    await handle_task(mock_stream, req)

    sent_data = mock_stream.get_sent_data()
    messages = []
    pos = 0
    while pos < len(sent_data):
        length = struct.unpack("!I", sent_data[pos : pos + 4])[0]
        payload = sent_data[pos + 4 : pos + 4 + length]
        messages.append(msgpack.unpackb(payload, raw=False))
        pos += 4 + length

    # All messages should have the same request_id
    for msg in messages:
        assert msg["request_id"] == "preserve-test"
