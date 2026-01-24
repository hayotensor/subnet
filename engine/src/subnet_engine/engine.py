import logging
import os

import trio

from subnet_engine.coordinator import EngineClient
from subnet_engine.framing import recv_msg, send_msg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("engine")

# Default configuration
ENGINE_SOCKET_PATH = os.environ.get("ENGINE_SOCKET_PATH", "/tmp/engine.sock")
APP_SOCKET_PATH = os.environ.get("APP_SOCKET_PATH", "/tmp/app.sock")


async def handle_connection(stream):
    """Handle an incoming client connection (from Network)."""
    client_id = stream.socket.getpeername() if hasattr(stream, "socket") else "unknown"
    logger.info(f"New connection from {client_id}")
    async with trio.open_nursery() as nursery:
        while True:
            try:
                req = await recv_msg(stream)
                if req is None:
                    break
                nursery.start_soon(handle_task, stream, req)
            except trio.EndOfChannel:
                logger.info(f"Connection closed by {client_id}")
                break
            except Exception as e:
                logger.error(f"Error handling connection: {e}")
                break


async def handle_task(stream, req):
    """Proxy a single task request to the App."""
    request_id = req.get("request_id")

    if not request_id:
        logger.warning("Received request without request_id")
        return

    logger.debug(f"Proxying task {request_id} to App")

    # Connect to App
    # In a production system, you might want a connection pool here.
    app_client = EngineClient(socket_path=APP_SOCKET_PATH)

    try:
        # We need to manually manage the connection because EngineClient.submit_task
        # is a generator that expects us to drive it, but here we want to just
        # forward the raw request dictionary or re-construct it.
        # Actually, EngineClient.submit_task takes a payload string and wraps it.
        # But we have a raw 'req' dict here.

        # Let's use a lower-level approach or reusing EngineClient methods carefully.
        # EngineClient.submit_task sends: {"request_id":..., "task_type":"generic", "payload":...}
        # We generally want to forward the 'req' exactly as is?
        # If 'req' comes from Network's EngineClient, it matches the format.

        # Let's verify if we can just forward 'req' as is.
        # EngineClient logic:
        # await send_msg(stream, req)
        # while True: msg = await recv_msg(stream); yield msg

        await app_client.connect()
        # We need to access the underlying stream to send the raw req dict
        # EngineClient._stream is internal but we can use it or extend the class.
        # For simplicity, let's just do manual forwarding here reusing framing.

        app_stream = app_client._stream
        await send_msg(app_stream, req)

        while True:
            msg = await recv_msg(app_stream)
            if msg is None:
                # App closed connection
                break

            # Forward response to Network
            await send_msg(stream, msg)

            if msg.get("type") in ("done", "error"):
                break

        logger.info(f"Task {request_id} proxy complete")

    except Exception as e:
        logger.error(f"Error proxying task {request_id}: {e}")
        try:
            await send_msg(
                stream,
                {
                    "request_id": request_id,
                    "type": "error",
                    "message": f"Proxy Error: {str(e)}",
                },
            )
        except Exception:
            pass
    finally:
        # Close connection to app? EngineClient logic is persistent but here we made a new one.
        # Ideally we close it.
        if app_client._stream:
            await app_client._stream.aclose()


async def open_unix_listener(path):
    """Create a high-level Unix socket listener."""
    sock = trio.socket.socket(trio.socket.AF_UNIX, trio.socket.SOCK_STREAM)
    await sock.bind(path)
    sock.listen()
    return [trio.SocketListener(sock)]


async def main():
    """Start the engine server."""
    # Clean up previous socket
    if os.path.exists(ENGINE_SOCKET_PATH):
        try:
            os.unlink(ENGINE_SOCKET_PATH)
            logger.info(f"Cleaned up existing socket at {ENGINE_SOCKET_PATH}")
        except OSError as e:
            logger.error(f"Failed to unlink socket: {e}")
            return

    try:
        listeners = await open_unix_listener(ENGINE_SOCKET_PATH)
        logger.info(f"Engine listening on {ENGINE_SOCKET_PATH}")
        await trio.serve_listeners(handle_connection, listeners)
    except Exception as e:
        logger.critical(f"Engine failed: {e}")
    finally:
        if os.path.exists(ENGINE_SOCKET_PATH):
            try:
                os.unlink(ENGINE_SOCKET_PATH)
                logger.info(f"Cleaned up socket at {ENGINE_SOCKET_PATH}")
            except OSError:
                pass


if __name__ == "__main__":
    try:
        trio.run(main)
    except KeyboardInterrupt:
        logger.info("Engine stopped by user")
