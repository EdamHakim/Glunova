.PHONY: backend-up backend-down backend-logs backend-rebuild backend-local backend-local-unix

backend-up:
	docker compose up django_app fastapi_ai

backend-down:
	docker compose down

backend-logs:
	docker compose logs -f django_app fastapi_ai

backend-rebuild:
	docker compose up --build -d django_app fastapi_ai

backend-local:
	scripts\\start_backends_local.bat

backend-local-unix:
	bash scripts/start_backends_local.sh
