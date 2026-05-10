SHELL := /bin/sh

PYTHON ?= python3
HOST ?= 0.0.0.0
PORT ?= 8000
VENV := backend/.venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
PYTHONPATH := backend/src
MANAGE := $(VENV_PYTHON) backend/manage.py

.PHONY: install install-python install-frontend build start test clean

install: install-python install-frontend

install-python:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install -r backend/requirements.txt

install-frontend:
	cd frontend && npm ci

build:
	cd frontend && npm run build

start: build
	$(MANAGE) runserver $(HOST):$(PORT)

test:
	PYTHONPATH=$(PYTHONPATH) $(VENV_PYTHON) -m pytest backend

clean:
	rm -rf backend/frontend_dist frontend/dist
