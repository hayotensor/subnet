"""Integration tests for the complete engine-coordinator system."""

import os

import pytest
import trio
from subnet_engine.coordinator import EngineClient
from subnet_engine.engine import handle_connection as engine_handle_connection
from subnet_engine.engine import open_unix_listener
from subnet_engine.framing import recv_msg, send_msg


# Mock App to handle requests from Proxy
async def mock_app_handler(stream):
    async with trio.open_nursery() as nursery:
        while True:
            try:
                req = await recv_msg(stream)
                if req is None:
                    break

                # Simple logic for testing: word splitter
                request_id = req.get("request_id")
                payload = req.get("payload", "")

                for chunk in payload.split():
                    await send_msg(
                        stream,
                        {"request_id": request_id, "type": "chunk", "data": chunk},
                    )

                await send_msg(stream, {"request_id": request_id, "type": "done"})

            except trio.EndOfChannel:
                break
            except Exception:
                break


@pytest.mark.trio
async def test_full_communication_flow(temp_socket_path):
    """Test complete communication between engine and coordinator."""
    results = []

    # Use distinct paths for engine and app sockets in test
    engine_sock = temp_socket_path + ".engine"
    app_sock = temp_socket_path + ".app"

    # We need to monkeypatch the SOCKET_PATHS or pass them if possible.
    # Since they are globals in engine.py and we import the function that uses globals
    # (handle_task internally uses EngineClient with global), we might need to mock
    # os.environ or patch the module globals.

    # Actually engine.engine.APP_SOCKET_PATH is what handle_task uses.
    # Let's patch it.
    from engine import engine

    original_app_path = engine.APP_SOCKET_PATH
    engine.APP_SOCKET_PATH = app_sock

    async def run_app(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(app_sock)
        task_status.started()
        try:
            await trio.serve_listeners(mock_app_handler, listeners)
        finally:
            listeners[0].socket.close()

    async def run_engine(task_status=trio.TASK_STATUS_IGNORED):
        """Run the engine server."""
        listeners = await open_unix_listener(engine_sock)
        task_status.started()
        try:
            await trio.serve_listeners(engine_handle_connection, listeners)
        finally:
            listeners[0].socket.close()

    async def run_coordinator():
        """Run the coordinator client."""
        client = EngineClient(engine_sock)
        async for chunk in client.submit_task("hello world"):
            results.append(chunk)

    try:
        async with trio.open_nursery() as nursery:
            # Start App
            await nursery.start(run_app)

            # Start Engine
            await nursery.start(run_engine)

            # Give time to start
            await trio.sleep(0.1)

            # Run coordinator
            await run_coordinator()

            nursery.cancel_scope.cancel()
    finally:
        engine.APP_SOCKET_PATH = original_app_path
        if os.path.exists(engine_sock):
            os.unlink(engine_sock)
        if os.path.exists(app_sock):
            os.unlink(app_sock)

    # Verify results
    assert results == ["hello", "world"]


@pytest.mark.trio
async def test_multiple_sequential_tasks(temp_socket_path):
    """Test multiple sequential tasks on the same connection."""
    engine_sock = temp_socket_path + ".engine"
    app_sock = temp_socket_path + ".app"

    from engine import engine

    original_app_path = engine.APP_SOCKET_PATH
    engine.APP_SOCKET_PATH = app_sock

    async def run_app(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(app_sock)
        task_status.started()
        try:
            await trio.serve_listeners(mock_app_handler, listeners)
        finally:
            listeners[0].socket.close()

    async def run_engine(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(engine_sock)
        task_status.started()
        try:
            await trio.serve_listeners(engine_handle_connection, listeners)
        finally:
            listeners[0].socket.close()

    async def run_multiple_tasks():
        client = EngineClient(engine_sock)
        # First task
        results1 = []
        async for chunk in client.submit_task("first task"):
            results1.append(chunk)
        # Second task
        results2 = []
        async for chunk in client.submit_task("second task"):
            results2.append(chunk)
        return results1, results2

    try:
        async with trio.open_nursery() as nursery:
            await nursery.start(run_app)
            await nursery.start(run_engine)
            await trio.sleep(0.1)
            results1, results2 = await run_multiple_tasks()
            nursery.cancel_scope.cancel()
    finally:
        engine.APP_SOCKET_PATH = original_app_path
        if os.path.exists(engine_sock):
            os.unlink(engine_sock)
        if os.path.exists(app_sock):
            os.unlink(app_sock)

    assert results1 == ["first", "task"]
    assert results2 == ["second", "task"]


@pytest.mark.trio
async def test_concurrent_clients(temp_socket_path):
    """Test multiple concurrent clients connecting to the engine."""
    all_results = []
    engine_sock = temp_socket_path + ".engine"
    app_sock = temp_socket_path + ".app"

    from engine import engine

    original_app_path = engine.APP_SOCKET_PATH
    engine.APP_SOCKET_PATH = app_sock

    async def run_app(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(app_sock)
        task_status.started()
        try:
            await trio.serve_listeners(mock_app_handler, listeners)
        finally:
            listeners[0].socket.close()

    async def run_engine(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(engine_sock)
        task_status.started()
        try:
            await trio.serve_listeners(engine_handle_connection, listeners)
        finally:
            listeners[0].socket.close()

    async def run_client(client_id):
        client = EngineClient(engine_sock)
        results = []
        async for chunk in client.submit_task(f"client {client_id}"):
            results.append(chunk)
        all_results.append((client_id, results))

    try:
        async with trio.open_nursery() as nursery:
            await nursery.start(run_app)
            await nursery.start(run_engine)
            await trio.sleep(0.1)

            async with trio.open_nursery() as client_nursery:
                client_nursery.start_soon(run_client, 1)
                client_nursery.start_soon(run_client, 2)
                client_nursery.start_soon(run_client, 3)

            nursery.cancel_scope.cancel()
    finally:
        engine.APP_SOCKET_PATH = original_app_path
        if os.path.exists(engine_sock):
            os.unlink(engine_sock)
        if os.path.exists(app_sock):
            os.unlink(app_sock)

    assert len(all_results) == 3
    for client_id, results in all_results:
        assert results == ["client", str(client_id)]


@pytest.mark.trio
async def test_empty_payload(temp_socket_path):
    """Test handling of empty payload."""
    results = []
    engine_sock = temp_socket_path + ".engine"
    app_sock = temp_socket_path + ".app"

    from engine import engine

    original_app_path = engine.APP_SOCKET_PATH
    engine.APP_SOCKET_PATH = app_sock

    async def run_app(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(app_sock)
        task_status.started()
        try:
            await trio.serve_listeners(mock_app_handler, listeners)
        finally:
            listeners[0].socket.close()

    async def run_engine(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(engine_sock)
        task_status.started()
        try:
            await trio.serve_listeners(engine_handle_connection, listeners)
        finally:
            listeners[0].socket.close()

    async def run_coordinator():
        client = EngineClient(engine_sock)
        async for chunk in client.submit_task(""):
            results.append(chunk)

    try:
        async with trio.open_nursery() as nursery:
            await nursery.start(run_app)
            await nursery.start(run_engine)
            await trio.sleep(0.1)
            await run_coordinator()
            nursery.cancel_scope.cancel()
    finally:
        engine.APP_SOCKET_PATH = original_app_path
        if os.path.exists(engine_sock):
            os.unlink(engine_sock)
        if os.path.exists(app_sock):
            os.unlink(app_sock)

    assert results == []


@pytest.mark.trio
async def test_large_payload(temp_socket_path):
    """Test handling of large payloads."""
    words = ["word" + str(i) for i in range(100)]
    payload = " ".join(words)
    results = []

    engine_sock = temp_socket_path + ".engine"
    app_sock = temp_socket_path + ".app"

    from engine import engine

    original_app_path = engine.APP_SOCKET_PATH
    engine.APP_SOCKET_PATH = app_sock

    async def run_app(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(app_sock)
        task_status.started()
        try:
            await trio.serve_listeners(mock_app_handler, listeners)
        finally:
            listeners[0].socket.close()

    async def run_engine(task_status=trio.TASK_STATUS_IGNORED):
        listeners = await open_unix_listener(engine_sock)
        task_status.started()
        try:
            await trio.serve_listeners(engine_handle_connection, listeners)
        finally:
            listeners[0].socket.close()

    async def run_coordinator():
        client = EngineClient(engine_sock)
        async for chunk in client.submit_task(payload):
            results.append(chunk)

    try:
        async with trio.open_nursery() as nursery:
            await nursery.start(run_app)
            await nursery.start(run_engine)
            await trio.sleep(0.1)
            await run_coordinator()
            nursery.cancel_scope.cancel()
    finally:
        engine.APP_SOCKET_PATH = original_app_path
        if os.path.exists(engine_sock):
            os.unlink(engine_sock)
        if os.path.exists(app_sock):
            os.unlink(app_sock)

    assert len(results) == 100
    assert results == words
