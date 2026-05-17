up:
	docker compose up -d

down:
	docker compose down

pull-models:
	docker exec -it redmine-rag-ollama ollama pull qwen3:4b
	docker exec -it redmine-rag-ollama ollama pull nomic-embed-text

venv:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

sync:
	. .venv/bin/activate && python scripts/sync_redmine.py

index:
	. .venv/bin/activate && python scripts/build_index.py

ask:
	. .venv/bin/activate && python scripts/ask.py
