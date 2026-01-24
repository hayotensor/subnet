import logging

import trio

logger = logging.getLogger("app.model")


class MockLLM:
    def __init__(self, model_name="gpt2-mock"):
        self.model_name = model_name
        logger.info(f"Loading model {model_name}...")
        pass

    async def generate(self, prompt: str):
        """Mock generation yielding chunks."""
        await trio.sleep(0.5)
        tokens = [
            "This ",
            "is ",
            "a ",
            "generated ",
            "response ",
            "from ",
            self.model_name,
        ]
        for token in tokens:
            await trio.sleep(0.1)
            yield token


class ModelRegistry:
    def __init__(self):
        self.models = {}

    def register(self, name: str, model: MockLLM):
        self.models[name] = model
        logger.info(f"Registered model: {name}")

    def get_model(self, name: str):
        return self.models.get(name)
