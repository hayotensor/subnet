import time
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TaskRequest:
    """
    Standard request envelope for subnet tasks.

    Examples:
        # Generic Inference
        req = TaskRequest(
            request_id="req-123",
            task_type="generate",
            payload='{"prompt": "The future of AI is", "model": "gpt2"}',
            metadata={"priority": "high"}
        )

        # Forward Pass
        req = TaskRequest(
            request_id="req-124",
            task_type="forward",
            payload="<input_tensor_bytes>",
            metadata={"layer": "4", "prev_node": "node-7"}
        )
    """

    request_id: str
    task_type: Literal["generic"]
    payload: str
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    timeout: float | None = None
    version: int = 1


@dataclass
class TaskResponse:
    request_id: str
    type: Literal["chunk", "done", "error"]
    data: str | None = None
    status_code: int = 200
    metadata: dict[str, str] = field(default_factory=dict)
