import logging
import os
import configparser
import json

from starlette.applications import Starlette
from starlette.responses import StreamingResponse, JSONResponse
from starlette.routing import Route
import uvicorn
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("engine")


def load_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.ini"
    )
    config.read(config_path)
    return config


config = load_config()
ENGINE_HOST = config.get("engine", "host", fallback="127.0.0.1")
ENGINE_PORT = config.getint("engine", "port", fallback=5000)
ALLOWED_IPS = [
    ip.strip()
    for ip in config.get("engine", "allowed_ips", fallback="127.0.0.1").split(",")
]

APP_HOST = config.get("app", "host", fallback="127.0.0.1")
APP_PORT = config.getint("app", "port", fallback=5001)
APP_URL = f"http://{APP_HOST}:{APP_PORT}/jsonrpc"


async def jsonrpc_endpoint(request):
    """Proxy JSON-RPC 2.0 requests to the App via HTTP."""
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

    logger.debug(f"Proxying task {req_id} to App at {APP_URL}")

    async def proxy_generator():
        """Connect to App via HTTP and proxy the streaming response."""
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", APP_URL, json=rpc_req) as response:
                    if response.status_code != 200:
                        err_msg = await response.aread()
                        yield (
                            json.dumps(
                                {
                                    "jsonrpc": "2.0",
                                    "error": {
                                        "code": -32000,
                                        "message": f"App Error: {err_msg.decode()}",
                                    },
                                    "id": req_id,
                                }
                            )
                            + "\n"
                        )
                        return

                    async for line in response.aiter_lines():
                        if line:
                            yield line + "\n"
        except Exception as e:
            logger.error(f"Error proxying task {req_id}: {e}")
            yield (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": f"Proxy Error: {str(e)}"},
                        "id": req_id,
                    }
                )
                + "\n"
            )

    return StreamingResponse(proxy_generator(), media_type="application/x-jsonlines")


routes = [
    Route("/jsonrpc", jsonrpc_endpoint, methods=["POST"]),
]

app = Starlette(debug=True, routes=routes)


def main():
    """Start the engine server with uvicorn."""
    logger.info(f"Engine starting on {ENGINE_HOST}:{ENGINE_PORT}")
    uvicorn.run(app, host=ENGINE_HOST, port=ENGINE_PORT, log_level="info")


if __name__ == "__main__":
    main()
