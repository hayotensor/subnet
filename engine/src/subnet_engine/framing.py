import struct

import msgpack
import trio


async def receive_exactly(stream, n):
    """Receive exactly n bytes from a Trio stream."""
    buf = bytearray()
    while len(buf) < n:
        chunk = await stream.receive_some(n - len(buf))
        if not chunk:
            raise trio.EndOfChannel
        buf.extend(chunk)
    return bytes(buf)


async def send_msg(stream, obj):
    data = msgpack.packb(obj, use_bin_type=True)
    await stream.send_all(struct.pack("!I", len(data)) + data)


async def recv_msg(stream):
    try:
        header = await receive_exactly(stream, 4)
        size = struct.unpack("!I", header)[0]
        payload = await receive_exactly(stream, size)
        return msgpack.unpackb(payload, raw=False)
    except trio.EndOfChannel:
        return None
