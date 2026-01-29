setup:
	python3 -m venv .venv
	./.venv/bin/pip install -e network
	./.venv/bin/pip install -e consensus
	./.venv/bin/pip install -e engine
	./.venv/bin/pip install -e app

lint:
	./.venv/bin/ruff check .

format:
	./.venv/bin/ruff format .

run-engine:
	./.venv/bin/python3 -m subnet_engine.engine

run-app:
	./.venv/bin/python3 -m subnet_app.server

run-coordinator:
	./.venv/bin/python3 -m subnet_engine.coordinator

run-consensus:
	./.venv/bin/python3 -m subnet_consensus.main

clean:
	rm -rf build/ dist/ *.egg-info .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f .ruff_cache
