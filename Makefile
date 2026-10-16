.PHONY: run

run:
	uv run uvicorn app.main:app --reload

