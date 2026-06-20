PYTHON := python3
VENV := .venv
ACTIVATE := . $(VENV)/bin/activate

.PHONY: setup run call health sync-agent freeze clean

SCENARIO ?=
CONTACT ?=
RUN_ARGS := $(if $(SCENARIO),--scenario $(SCENARIO),)
CALL_ARGS := $(if $(SCENARIO),--scenario $(SCENARIO),) $(if $(CONTACT),--contact $(CONTACT),)

setup:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE) && python -m pip install --upgrade pip
	$(ACTIVATE) && pip install -r requirements.txt

run:
	$(ACTIVATE) && python run_server.py $(RUN_ARGS)

call:
	$(ACTIVATE) && python run_calls.py $(CALL_ARGS)

health:
	$(ACTIVATE) && python -c "import httpx; from app.config import get_settings; p=get_settings().app_port; print(httpx.get(f'http://127.0.0.1:{p}/health', timeout=5).text)"

sync-agent:
	$(ACTIVATE) && python sync_agent.py $(RUN_ARGS)

freeze:
	$(ACTIVATE) && pip freeze

clean:
	rm -rf $(VENV) __pycache__ app/__pycache__
