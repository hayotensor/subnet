import logging

from subnet_engine.protocol import TaskRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.handler")


async def handle_generic_task(req: TaskRequest, send_response_func, model_registry):
    """
    Process a generic task request.

    :param req: The TaskRequest object
    :param send_response_func: A generic async function to send responses back (chunks/done/error)
    :param model_registry: The ModelRegistry instance
    """
    logger.info(f"Processing generic task {req.request_id}")
    logger.info(f"Request data: {req}")

    try:
        # Parse payload to determine model and actual prompt
        import json

        model_name = "gpt2"
        prompt = req.payload

        try:
            data = json.loads(req.payload)
            if isinstance(data, dict):
                model_name = data.get("model", "gpt2")
                prompt = data.get("prompt", "")
        except json.JSONDecodeError:
            pass

        model_instance = model_registry.get_model(model_name)

        if not model_instance:
            raise ValueError(f"Model '{model_name}' not found.")

        # Use the injected model to generate response
        async for chunk in model_instance.generate(prompt):
            await send_response_func(
                {"request_id": req.request_id, "type": "chunk", "data": chunk}
            )

        await send_response_func({"request_id": req.request_id, "type": "done"})
        logger.info(f"Task {req.request_id} completed")
    except Exception as e:
        logger.error(f"Error processing task {req.request_id}: {e}")
        try:
            await send_response_func(
                {"request_id": req.request_id, "type": "error", "message": str(e)}
            )
        except Exception:
            pass
