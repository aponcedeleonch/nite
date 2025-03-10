.PHONY: install, clean, typecheck, lint, format

# Default port for the web server
PORT?=9090

install:
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
