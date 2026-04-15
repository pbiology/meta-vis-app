SHELL := /bin/bash

COMPOSE := docker compose
BACKEND_SERVICE := backend

ADMIN_USERNAME ?= admin
ADMIN_PASSWORD ?= yourpassword
ADMIN_ROLE ?= admin

NEW_USERNAME ?= user
NEW_PASSWORD ?= yourpassword
NEW_ROLE ?= reader

.PHONY: help dev dev-build up up-build build rebuild down reset logs ps restart \
        backend-shell frontend-shell mongo-shell minio-logs \
        init-db create-admin create-user load-taxonomy \
        test lint format

help:
	@echo "Available targets:"
	@echo "  make dev              Start full dev stack in foreground"
	@echo "  make dev-build        Start full dev stack in foreground and rebuild images"
	@echo "  make up               Start full dev stack in background"
	@echo "  make up-build         Start full dev stack in background and rebuild images"
	@echo "  make build            Build images"
	@echo "  make rebuild          Rebuild images without cache"
	@echo "  make down             Stop containers, keep volumes"
	@echo "  make reset            Stop containers and remove volumes"
	@echo "  make logs             Follow all service logs"
	@echo "  make ps               Show service status"
	@echo "  make restart          Restart the stack in background"
	@echo ""
	@echo "  make backend-shell    Open a shell in the backend container"
	@echo "  make frontend-shell   Open a shell in the frontend container"
	@echo "  make mongo-shell      Open mongosh in the Mongo container"
	@echo "  make minio-logs       Show MinIO logs"
	@echo ""
	@echo "  make init-db          Create admin user and load taxonomy"
	@echo "  make create-admin     Create admin user"
	@echo "  make create-user      Create a user with NEW_USERNAME/NEW_PASSWORD/NEW_ROLE"
	@echo "  make load-taxonomy    Download and load NCBI taxonomy"
	@echo ""
	@echo "Examples:"
	@echo "  make up"
	@echo "  make up-build"
	@echo "  make dev"
	@echo "  make init-db ADMIN_USERNAME=admin ADMIN_PASSWORD=supersecret"
	@echo "  make create-user NEW_USERNAME=alice NEW_PASSWORD=secret NEW_ROLE=writer"

dev:
	$(COMPOSE) up

dev-build:
	$(COMPOSE) up --build

up:
	$(COMPOSE) up -d

up-build:
	$(COMPOSE) up -d --build

build:
	$(COMPOSE) build

rebuild:
	$(COMPOSE) build --no-cache

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

restart:
	$(COMPOSE) down
	$(COMPOSE) up -d

backend-shell:
	$(COMPOSE) exec $(BACKEND_SERVICE) /bin/bash

frontend-shell:
	$(COMPOSE) exec frontend /bin/sh

mongo-shell:
	$(COMPOSE) exec mongodb mongosh -u admin -p "$$MONGO_ROOT_PASSWORD" --authenticationDatabase admin

minio-logs:
	$(COMPOSE) logs -f minio

create-admin:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) python create_user.py \
		--username "$(ADMIN_USERNAME)" \
		--password "$(ADMIN_PASSWORD)" \
		--role "$(ADMIN_ROLE)"

create-user:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) python create_user.py \
		--username "$(NEW_USERNAME)" \
		--password "$(NEW_PASSWORD)" \
		--role "$(NEW_ROLE)"

load-taxonomy:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) python load_taxonomy.py

init-db: create-admin load-taxonomy

test:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) pytest

lint:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) ruff check .
	$(COMPOSE) exec -T $(BACKEND_SERVICE) mypy .

format:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) ruff check --fix .