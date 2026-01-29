import logging
import os
import configparser
import json

from starlette.applications import Starlette
from starlette.responses import StreamingResponse, JSONResponse
from starlette.routing import Route
import uvicorn

from subnet_engine.protocol import TaskRequest
from subnet_app.handler import handle_generic_task
from subnet_app.model import MockLLM, ModelRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.server")


def load_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.ini"
    )
    config.read(config_path)
    return config


config = load_config()
APP_HOST = config.get("app", "host", fallback="127.0.0.1")
APP_PORT = config.getint("app", "port", fallback=5001)
ALLOWED_IPS = [
    ip.strip()
    for ip in config.get("app", "allowed_ips", fallback="127.0.0.1").split(",")
]

# In-memory model registry
registry = ModelRegistry()
registry.register("gpt2", MockLLM("gpt2"))
registry.register("llama3", MockLLM("llama3"))


async def jsonrpc_endpoint(request):
    """Handle JSON-RPC 2.0 requests via HTTP POST."""
    client_host = request.client.host if request.client else "127.0.0.1"
    if client_host not in ALLOWED_IPS and client_host not in (
        "127.0.0.1",
        "localhost",
        "testclient",
    ):
        logger.warning(f"Connection from disallowed IP: {client_host}")
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        rpc_req = await request.json()
    except Exception:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
                "id": None,
            },
            status_code=400,
        )

    # Validate JSON-RPC 2.0
    if rpc_req.get("jsonrpc") != "2.0":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": rpc_req.get("id"),
            },
            status_code=400,
        )

    method = rpc_req.get("method")
    params = rpc_req.get("params", {})
    req_id = rpc_req.get("id")

    if method != "submit_task":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "Method not found"},
                "id": req_id,
            },
            status_code=404,
        )

    # Transform params to TaskRequest
    try:
        req = TaskRequest(
            request_id=str(req_id),
            task_type=params.get("task_type", "generic"),
            payload=params.get("payload", ""),
        )
    except Exception as e:
        logger.error(f"Invalid parameters: {e}")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "Invalid params"},
                "id": req_id,
            },
            status_code=400,
        )

    async def response_generator():
        """Generator to yield JSON-RPC results as lines (streaming)."""
        import anyio

        send_chan, recv_chan = anyio.create_memory_object_stream()

        async def send_response_func(obj):
            response = {"jsonrpc": "2.0", "result": obj, "id": req_id}
            await send_chan.send(json.dumps(response) + "\n")

        async with anyio.create_task_group() as tg:
            tg.start_soon(handle_generic_task, req, send_response_func, registry)

            # Close the channel once the task is done
            # Note: handle_generic_task doesn't return until it completes its logic
            # but it yields multiple times via send_response_func.
            # We need to signal the end of the generator.
            # The handler sends 'done' as the final message.

            async for msg in recv_chan:
                yield msg
                if '"type": "done"' in msg or '"type": "error"' in msg:
                    break

    return StreamingResponse(response_generator(), media_type="application/x-jsonlines")


routes = [
    Route("/jsonrpc", jsonrpc_endpoint, methods=["POST"]),
]

app = Starlette(debug=True, routes=routes)


def main():
    """Start the app server with uvicorn."""
    logger.info(f"App starting on {APP_HOST}:{APP_PORT}")
    uvicorn.run(app, host=APP_HOST, port=APP_PORT, log_level="info")


if __name__ == "__main__":
    logger.info("App stopped by user")
