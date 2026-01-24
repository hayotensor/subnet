import functools
import logging
import os

import trio
from subnet_engine.framing import recv_msg, send_msg
from subnet_engine.protocol import TaskRequest

from subnet_app.handler import handle_generic_task
from subnet_app.model import MockLLM, ModelRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.server")

APP_SOCKET_PATH = os.environ.get("APP_SOCKET_PATH", "/tmp/app.sock")


async def handle_connection(stream, model_registry):
    """Handle an incoming engine connection."""
    client_id = stream.socket.getpeername() if hasattr(stream, "socket") else "unknown"
    logger.info(f"New connection from {client_id}")
    async with trio.open_nursery() as nursery:
        while True:
            try:
                req_dict = await recv_msg(stream)
                if req_dict is None:
                    break

                # Transform dict to TaskRequest
                try:
                    req = TaskRequest(**req_dict)
                except Exception as e:
                    logger.error(f"Invalid request format: {e}")
                    continue

                # Define a sender function to pass to the handler
                async def send_response(obj):
                    await send_msg(stream, obj)

                # Inject registry
                nursery.start_soon(
                    handle_generic_task, req, send_response, model_registry
                )
            except trio.EndOfChannel:
                logger.info(f"Connection closed by {client_id}")
                break
            except Exception as e:
                logger.error(f"Error handling connection: {e}")
                break


async def open_unix_listener(path):
    """Create a high-level Unix socket listener."""
    sock = trio.socket.socket(trio.socket.AF_UNIX, trio.socket.SOCK_STREAM)
    await sock.bind(path)
    sock.listen()
    return [trio.SocketListener(sock)]


async def main():
    """Start the app server."""
    # 1. Load Resources
    logger.info("Initializing Model Registry...")
    registry = ModelRegistry()

    # Load multiple models
    registry.register("gpt2", MockLLM("gpt2"))
    registry.register("llama3", MockLLM("llama3"))

    logger.info("Models loaded.")

    # Clean up previous socket
    if os.path.exists(APP_SOCKET_PATH):
        try:
            os.unlink(APP_SOCKET_PATH)
            logger.info(f"Cleaned up existing socket at {APP_SOCKET_PATH}")
        except OSError as e:
            logger.error(f"Failed to unlink socket: {e}")
            return

    try:
        listeners = await open_unix_listener(APP_SOCKET_PATH)
        logger.info(f"App listening on {APP_SOCKET_PATH}")

        # Pass registry using partial
        handler_with_registry = functools.partial(
            handle_connection, model_registry=registry
        )

        await trio.serve_listeners(handler_with_registry, listeners)
    except Exception as e:
        logger.critical(f"App failed: {e}")
    finally:
        if os.path.exists(APP_SOCKET_PATH):
            try:
                os.unlink(APP_SOCKET_PATH)
                logger.info(f"Cleaned up socket at {APP_SOCKET_PATH}")
            except OSError:
                pass


if __name__ == "__main__":
    try:
        trio.run(main)
    except KeyboardInterrupt:
        logger.info("App stopped by user")
