import logging
import os
import uuid

import trio

from subnet_engine.framing import recv_msg, send_msg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("coordinator")

# Default configuration
SOCKET_PATH = os.environ.get("ENGINE_SOCKET_PATH", "/tmp/engine.sock")
RETRY_INTERVAL = float(os.environ.get("RETRY_INTERVAL", "2.0"))


class EngineClient:
    def __init__(self, socket_path=SOCKET_PATH):
        self.socket_path = socket_path
        self._stream = None

    async def connect(self):
        """Connect to the engine with retries."""
        while True:
            try:
                self._stream = await trio.open_unix_socket(self.socket_path)
                logger.info(f"Connected to engine at {self.socket_path}")
                return
            except (OSError, trio.BrokenResourceError):
                logger.warning(
                    f"Failed to connect to engine. Retrying in {RETRY_INTERVAL}s..."
                )
                await trio.sleep(RETRY_INTERVAL)

    async def submit_task(self, payload: str):
        """Submit a task and yield results."""
        while True:
            if not self._stream:
                await self.connect()

            request_id = str(uuid.uuid4())
            try:
                await send_msg(
                    self._stream,
                    {
                        "request_id": request_id,
                        "task_type": "generic",
                        "payload": payload,
                    },
                )

                while True:
                    msg = await recv_msg(self._stream)
                    if msg is None:
                        logger.warning(
                            "Engine connection lost while waiting for results"
                        )
                        self._stream = None
                        break

                    if msg.get("request_id") != request_id:
                        continue

                    if msg["type"] == "chunk":
                        yield msg["data"]
                    elif msg["type"] == "done":
                        logger.info(f"Task {request_id} complete")
                        return
                    elif msg["type"] == "error":
                        logger.error(f"Task {request_id} failed: {msg['message']}")
                        return

            except (trio.BrokenResourceError, trio.EndOfChannel):
                logger.warning("Connection to engine lost. Reconnecting...")
                self._stream = None
                # Loop will continue and call connect()


async def main():
    client = EngineClient()
    logger.info("Starting coordinator...")
    async for chunk in client.submit_task("this is a test payload"):
        print(f"chunk: {chunk}")


if __name__ == "__main__":
    try:
        trio.run(main)
    except KeyboardInterrupt:
        logger.info("Coordinator stopped by user")
