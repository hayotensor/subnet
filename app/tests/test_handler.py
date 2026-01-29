import json

import pytest
from subnet_app.handler import handle_generic_task
from subnet_engine.protocol import TaskRequest


class MockModel:
    async def generate(self, prompt):
        yield "chunk1"
        yield "chunk2"


class MockRegistry:
    def get_model(self, name):
        if name == "gpt2":
            return MockModel()
        return None


@pytest.mark.trio
async def test_handle_generic_task_default():
    """Test handler with plain text payload (default model)."""
    req = TaskRequest(request_id="test-1", task_type="generic", payload="hello world")
    results = []

    async def mock_send(obj):
        results.append(obj)

    registry = MockRegistry()
    await handle_generic_task(req, mock_send, registry)

    assert len(results) == 3
    assert results[0]["data"] == "chunk1"


@pytest.mark.trio
async def test_handle_generic_task_json():
    """Test handler with JSON payload specifying model."""
    payload = json.dumps({"model": "gpt2", "prompt": "hello"})
    req = TaskRequest(request_id="test-json", task_type="generic", payload=payload)
    results = []

    async def mock_send(obj):
        results.append(obj)

    registry = MockRegistry()
    await handle_generic_task(req, mock_send, registry)

    assert len(results) == 3
    assert results[0]["data"] == "chunk1"


@pytest.mark.trio
async def test_handle_unknown_model():
    """Test handling of unknown model."""
    payload = json.dumps({"model": "unknown", "prompt": "hello"})
    req = TaskRequest(request_id="test-err", task_type="generic", payload=payload)
    results = []

    async def mock_send(obj):
        results.append(obj)

    registry = MockRegistry()
    await handle_generic_task(req, mock_send, registry)

    assert len(results) == 1
    assert results[0]["type"] == "error"
    assert "not found" in results[0]["message"]
