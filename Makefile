.PHONY: install, clean, start-web

VENV?=venv

install:
	python3.12 -m venv ${VENV};
	source ./${VENV}/bin/activate; \
	pip install --upgrade pip; \
	pip install -e .; \

clean:
	rm -rf venv

start:
	source ./${VENV}/bin/activate; \
	cd web; \
	flask run --host=0.0.0.0 --port=8531

start-dev:
	source ./${VENV}/bin/activate; \
	cd web; \
	flask run --host=0.0.0.0 --port=8531 --debug
