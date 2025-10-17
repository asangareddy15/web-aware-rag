.PHONY: docker-compose
docker-compose:
	docker-compose up

.PHONY: run
run:
	uv run --env-file .env python cmd_server/server/main.py

.PHONY: run-worker
run-worker:
	uv run --env-file .env cmd_server/worker/main.py

.PHONY: import-path
import-path:
	$env:PYTHONPATH = "$PWD"