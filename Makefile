.PHONY: install, clean, typecheck, lint, test-setup, test-cleaning, start, start-dev

VENV?=venv

install:
	python3.12 -m venv ${VENV};
	source ./${VENV}/bin/activate; \
	pip install --upgrade pip; \
	pip install -e .; \

clean:
	rm -rf venv; \

test-setup:
	source ./${VENV}/bin/activate; \
	pip install -r test-requirements.txt; \

typecheck: test-setup
	mypy src;
	$(MAKE) test-cleaning

lint: test-setup
	flake8 src;
	$(MAKE) test-cleaning

test-cleaning:
	pip uninstall -r test-requirements.txt -y;

start:
	source ./${VENV}/bin/activate; \
	cd web; \
	flask run --host=0.0.0.0 --port=8531

start-dev:
	source ./${VENV}/bin/activate; \
	cd web; \
	flask run --host=0.0.0.0 --port=8531 --debug
