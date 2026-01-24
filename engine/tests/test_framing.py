"""Tests for the framing module."""

import struct

import msgpack
import pytest
import trio
from subnet_engine.framing import receive_exactly, recv_msg, send_msg


@pytest.mark.trio
async def test_send_msg_basic(mock_stream):
    """Test sending a simple message."""
    msg = {"hello": "world", "number": 42}
    await send_msg(mock_stream, msg)

    sent = mock_stream.get_sent_data()
    # First 4 bytes are length
    length = struct.unpack("!I", sent[:4])[0]
    # Remaining bytes are msgpack data
    payload = sent[4:]
    assert len(payload) == length
    assert msgpack.unpackb(payload, raw=False) == msg


@pytest.mark.trio
async def test_send_msg_empty_dict(mock_stream):
    """Test sending an empty dictionary."""
    msg = {}
    await send_msg(mock_stream, msg)

    sent = mock_stream.get_sent_data()
    _ = struct.unpack("!I", sent[:4])[0]
    payload = sent[4:]
    assert msgpack.unpackb(payload, raw=False) == msg


@pytest.mark.trio
async def test_send_msg_complex_nested(mock_stream):
    """Test sending a complex nested structure."""
    msg = {
        "request_id": "test-123",
        "data": {"nested": [1, 2, 3], "flag": True},
        "list": ["a", "b", "c"],
    }
    await send_msg(mock_stream, msg)

    sent = mock_stream.get_sent_data()
    _ = struct.unpack("!I", sent[:4])[0]
    payload = sent[4:]
    assert msgpack.unpackb(payload, raw=False) == msg


@pytest.mark.trio
async def test_recv_msg_basic(mock_stream):
    """Test receiving a simple message."""
    original_msg = {"test": "data", "value": 123}
    packed = msgpack.packb(original_msg, use_bin_type=True)
    frame = struct.pack("!I", len(packed)) + packed

    mock_stream.set_recv_data(frame)
    received = await recv_msg(mock_stream)
    assert received == original_msg


@pytest.mark.trio
async def test_recv_msg_empty_stream(mock_stream):
    """Test receiving from an empty stream returns None."""
    mock_stream.set_recv_data(b"")
    received = await recv_msg(mock_stream)
    assert received is None


@pytest.mark.trio
async def test_recv_msg_partial_header(mock_stream):
    """Test receiving with partial header data returns None."""
    # Only 2 bytes of the 4-byte header
    mock_stream.set_recv_data(b"\x00\x00")

    received = await recv_msg(mock_stream)
    assert received is None


@pytest.mark.trio
async def test_recv_msg_partial_payload(mock_stream):
    """Test receiving with partial payload returns None."""
    # Header says 100 bytes, but only provide 10
    header = struct.pack("!I", 100)
    mock_stream.set_recv_data(header + b"x" * 10)

    received = await recv_msg(mock_stream)
    assert received is None


@pytest.mark.trio
async def test_receive_exactly_full_data(mock_stream):
    """Test receive_exactly with complete data."""
    data = b"hello world"
    mock_stream.set_recv_data(data)
    received = await receive_exactly(mock_stream, len(data))
    assert received == data


@pytest.mark.trio
async def test_receive_exactly_chunked(mock_stream):
    """Test receive_exactly assembles chunks correctly."""

    class ChunkedStream:
        def __init__(self):
            self.chunks = [b"hel", b"lo ", b"wor", b"ld"]
            self.index = 0

        async def receive_some(self, max_bytes):
            if self.index >= len(self.chunks):
                return b""
            chunk = self.chunks[self.index]
            self.index += 1
            # Return at most max_bytes
            return chunk[:max_bytes]

    stream = ChunkedStream()
    received = await receive_exactly(stream, 11)
    assert received == b"hello world"


@pytest.mark.trio
async def test_receive_exactly_insufficient_data(mock_stream):
    """Test receive_exactly raises EndOfChannel when data runs out."""
    mock_stream.set_recv_data(b"short")

    with pytest.raises(trio.EndOfChannel):
        await receive_exactly(mock_stream, 100)


@pytest.mark.trio
async def test_send_recv_roundtrip(mock_stream):
    """Test sending and receiving a message in a roundtrip."""
    original_msg = {"request_id": "abc123", "type": "chunk", "data": "test data"}

    # Send the message
    await send_msg(mock_stream, original_msg)

    # Prepare the stream to receive what was sent
    mock_stream.set_recv_data(mock_stream.get_sent_data())

    # Receive the message
    received_msg = await recv_msg(mock_stream)
    assert received_msg == original_msg


@pytest.mark.trio
async def test_large_message(mock_stream):
    """Test sending and receiving a large message."""
    # Create a message with a large payload
    large_data = "x" * 10000
    msg = {"request_id": "large", "payload": large_data}

    await send_msg(mock_stream, msg)
    mock_stream.set_recv_data(mock_stream.get_sent_data())

    received = await recv_msg(mock_stream)
    assert received == msg
    assert len(received["payload"]) == 10000
