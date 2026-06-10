PYTHON := python3
VENV := .venv
ACTIVATE := . $(VENV)/bin/activate

.PHONY: setup run call health freeze clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE) && python -m pip install --upgrade pip
	$(ACTIVATE) && pip install -r requirements.txt

run:
	$(ACTIVATE) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

call:
	$(ACTIVATE) && python run_calls.py

health:
	$(ACTIVATE) && python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/health', timeout=5).text)"

freeze:
	$(ACTIVATE) && pip freeze

clean:
	rm -rf $(VENV) __pycache__ app/__pycache__
