.PHONY: install, clean, typecheck, lint, format

# Default port for the web server
PORT?=8787

install:
	sudo apt-get update && sudo apt-get upgrade -y; \
	sudo apt-get install -y libportaudio2 libportaudiocpp0 portaudio19-dev; \
	curl -LsSf https://astral.sh/uv/install.sh | sh; \
	uv sync --all-groups;

clean:
	rm -rf .venv;

typecheck:
	uv run mypy src;

test:
	uv run pytest tests;

lint:
	uv run ruff check;

format:
	uv run ruff format; \
	uv run ruff check --fix;

run_web:
	uvicorn nite.api.v1:app --host 0.0.0.0 --port ${PORT} --log-level debug

run_web_dev:
	uvicorn nite.api.v1:app --host 0.0.0.0 --port ${PORT} --reload  --log-level debug

all: format lint typecheck test
