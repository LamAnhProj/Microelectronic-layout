PYTHON ?= .venv/bin/python

.PHONY: doctor test index smoke layout-smoke worker-build worker-smoke qualify dashboard
dashboard:
	$(PYTHON) dashboard/server.py
doctor:
	$(PYTHON) -m chip_lab doctor
test:
	$(PYTHON) -m unittest discover -s tests -v
index:
	$(PYTHON) -m chip_lab index
smoke:
	$(PYTHON) -m chip_lab simulate
layout-smoke:
	$(PYTHON) -m chip_lab layout-smoke
worker-build:
	docker compose build worker
worker-smoke:
	mkdir -p runs
	docker compose run --rm worker
qualify:
	mkdir -p runs
	docker compose run --rm worker qualify --output /results
