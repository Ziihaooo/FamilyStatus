.PHONY: run test

run:
	uv run --env-file .env uvicorn app.main:app --reload

test:
	uv run pytest