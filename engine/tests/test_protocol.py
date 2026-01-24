"""Tests for the protocol module."""

from subnet_engine.protocol import TaskRequest, TaskResponse


def test_task_request_creation():
    """Test creating a TaskRequest."""
    req = TaskRequest(request_id="test-123", task_type="generic", payload="test data")
    assert req.request_id == "test-123"
    assert req.task_type == "generic"
    assert req.payload == "test data"


def test_task_request_fields():
    """Test TaskRequest has expected fields."""
    req = TaskRequest(request_id="abc", task_type="generic", payload="xyz")
    assert hasattr(req, "request_id")
    assert hasattr(req, "task_type")
    assert hasattr(req, "payload")


def test_task_response_chunk():
    """Test creating a TaskResponse with type 'chunk'."""
    resp = TaskResponse(request_id="test-456", type="chunk", data="chunk data")
    assert resp.request_id == "test-456"
    assert resp.type == "chunk"
    assert resp.data == "chunk data"


def test_task_response_done():
    """Test creating a TaskResponse with type 'done'."""
    resp = TaskResponse(request_id="test-789", type="done")
    assert resp.request_id == "test-789"
    assert resp.type == "done"
    assert resp.data is None


def test_task_response_error():
    """Test creating a TaskResponse with type 'error'."""
    resp = TaskResponse(request_id="test-error", type="error", data="error message")
    assert resp.request_id == "test-error"
    assert resp.type == "error"
    assert resp.data == "error message"


def test_task_response_default_data():
    """Test TaskResponse has None as default data."""
    resp = TaskResponse(request_id="id", type="done")
    assert resp.data is None


def test_task_request_literal_type():
    """Test TaskRequest task_type is properly typed."""
    # This test mainly validates that the type annotation exists
    # In a real application, you might use mypy or similar for static checking
    req = TaskRequest(request_id="id", task_type="generic", payload="data")
    assert req.task_type in ["generic"]


def test_task_response_literal_types():
    """Test TaskResponse type is properly typed."""
    chunk = TaskResponse(request_id="id", type="chunk", data="data")
    done = TaskResponse(request_id="id", type="done")
    error = TaskResponse(request_id="id", type="error", data="error")

    assert chunk.type in ["chunk", "done", "error"]
    assert done.type in ["chunk", "done", "error"]
    assert error.type in ["chunk", "done", "error"]
