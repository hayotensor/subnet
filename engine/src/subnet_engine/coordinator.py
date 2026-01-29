import logging
import os
import uuid
import configparser
import json

import httpx
import trio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("coordinator")


def load_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.ini"
    )
    config.read(config_path)
    return config


config = load_config()
DEFAULT_HOST = config.get("engine", "host", fallback="127.0.0.1")
DEFAULT_PORT = config.getint("engine", "port", fallback=5000)
RETRY_INTERVAL = config.getfloat("client", "retry_interval", fallback=2.0)


class EngineClient:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.url = f"http://{self.host}:{self.port}/jsonrpc"

    async def submit_task(self, payload: str):
        """Submit a task via HTTP JSON-RPC 2.0 and yield results."""
        request_id = str(uuid.uuid4())
        rpc_req = {
            "jsonrpc": "2.0",
            "method": "submit_task",
            "params": {
                "task_type": "generic",
                "payload": payload,
            },
            "id": request_id,
        }

        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "POST", self.url, json=rpc_req
                    ) as response:
                        if response.status_code != 200:
                            err_msg = await response.aread()
                            logger.error(
                                f"Engine request failed ({response.status_code}): {err_msg.decode()}"
                            )
                            return

                        async for line in response.aiter_lines():
                            if not line:
                                continue

                            try:
                                rpc_resp = json.loads(line)
                            except json.JSONDecodeError:
                                logger.error(f"Malformed JSON response: {line}")
                                continue

                            if rpc_resp.get("id") != request_id:
                                continue

                            if "error" in rpc_resp:
                                error = rpc_resp["error"]
                                logger.error(
                                    f"Task {request_id} failed: {error.get('message')}"
                                )
                                return

                            result = rpc_resp.get("result", {})

                            if result.get("type") == "chunk":
                                yield result["data"]
                            elif result.get("type") == "done":
                                logger.info(f"Task {request_id} complete")
                                return
                            elif result.get("type") == "error":
                                logger.error(
                                    f"Task {request_id} failed: {result.get('message')}"
                                )
                                return
                # If we get here without a 'done' or 'error', the connection was likely lost
                logger.warning(
                    "Engine connection lost while waiting for results. Retrying..."
                )
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.warning(
                    f"Failed to communicate with engine: {e}. Retrying in {RETRY_INTERVAL}s..."
                )
                await trio.sleep(RETRY_INTERVAL)


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
