.PHONY: backend-up backend-down backend-logs backend-rebuild backend-local backend-local-unix

backend-up:
	docker compose up --build django_app fastapi_ai nginx

backend-down:
	docker compose down

backend-logs:
	docker compose logs -f django_app fastapi_ai nginx

backend-rebuild:
	docker compose up --build -d django_app fastapi_ai nginx

backend-local:
	scripts\\start_backends_local.bat

