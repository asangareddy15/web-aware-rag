docker-compose: docker-compose up

run: uv run --env-file .env python app/main.py

import-path: $env:PYTHONPATH = "$PWD"