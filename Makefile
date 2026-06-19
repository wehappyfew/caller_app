PYTHON := python3
VENV := .venv
ACTIVATE := . $(VENV)/bin/activate

.PHONY: setup run call health sync-agent freeze clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE) && python -m pip install --upgrade pip
	$(ACTIVATE) && pip install -r requirements.txt

run:
	$(ACTIVATE) && uvicorn app.main:app --host 0.0.0.0 --port 8001

call:
	$(ACTIVATE) && python run_calls.py

health:
	$(ACTIVATE) && python -c "import httpx; from app.config import get_settings; p=get_settings().app_port; print(httpx.get(f'http://127.0.0.1:{p}/health', timeout=5).text)"

sync-agent:
	$(ACTIVATE) && python sync_agent.py

freeze:
	$(ACTIVATE) && pip freeze

clean:
	rm -rf $(VENV) __pycache__ app/__pycache__
