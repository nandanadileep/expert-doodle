.PHONY: install api sync

install:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

api:
	. venv/bin/activate && uvicorn main:app --reload --port 8000

sync:
	. venv/bin/activate && python run_daily.py
