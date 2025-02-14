.PHONY: install, clean, typecheck, lint, format

# Expected to be a path set by the user
# VENV?=~/py_venvs/nite_env
VENV?=./venv
PORT?=9090

install:
	python3.12 -m venv ${VENV};
	source ${VENV}/bin/activate; \
	pip install --upgrade pip; \
	pip install -e .; \

clean:
	rm -rf ${VENV}; \

typecheck:
	hatch run test:typing;

test:
	hatch run test:unit;

lint:
	hatch run style:check

format:
	hatch run style:format

run_web:
	uvicorn nite.api.v1:app --host 0.0.0.0 --port ${PORT}

run_web_dev:
	uvicorn nite.api.v1:app --host 0.0.0.0 --port ${PORT} --reload

all: format lint typecheck test
