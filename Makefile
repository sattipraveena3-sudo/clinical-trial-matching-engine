.PHONY: install test refresh run docker-up

install:
	python scripts/setup_local.py

test:
	pytest

refresh:
	python scripts/refresh_trials.py --max-studies 1000

run:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	docker compose up --build
