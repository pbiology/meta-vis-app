SHELL := /bin/bash

COMPOSE := docker compose
KC_COMPOSE := docker compose -f docker-compose.keycloak.yml
BACKEND_SERVICE := backend

.PHONY: help dev dev-build up up-build build rebuild down reset logs ps restart \
        backend-shell frontend-shell mongo-shell minio-logs \
        load-taxonomy \
        keycloak-up keycloak-down keycloak-logs keycloak-reset \
        test lint format \
        image-backend-stage image-frontend-stage \
        image-backend-prod image-frontend-prod

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
	@echo "  make load-taxonomy    Download and load NCBI taxonomy"
	@echo "  (users are managed via Keycloak — see 'make keycloak-up')"
	@echo ""
	@echo "  make keycloak-up      Start local Keycloak (detached) on :8081"
	@echo "  make keycloak-down    Stop Keycloak, keep volume"
	@echo "  make keycloak-logs    Follow Keycloak logs"
	@echo "  make keycloak-reset   Stop Keycloak and wipe its volume (re-imports realm)"
	@echo ""
	@echo "  make image-backend-stage   Build + push backend :stage image (linux/amd64)"
	@echo "  make image-frontend-stage  Build + push frontend :stage image (uses --mode stage)"
	@echo "  make image-backend-prod    Build + push backend :prod image"
	@echo "  make image-frontend-prod   Build + push frontend :prod image (uses --mode prod)"
	@echo ""
	@echo "Examples:"
	@echo "  make up"
	@echo "  make up-build"
	@echo "  make dev"
	@echo "  make keycloak-up"

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

load-taxonomy:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) python load_taxonomy.py

keycloak-up:
	$(KC_COMPOSE) up -d

keycloak-down:
	$(KC_COMPOSE) down

keycloak-logs:
	$(KC_COMPOSE) logs -f

keycloak-reset:
	$(KC_COMPOSE) down -v

test:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) pytest

lint:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) ruff check .
	$(COMPOSE) exec -T $(BACKEND_SERVICE) mypy .

format:
	$(COMPOSE) exec -T $(BACKEND_SERVICE) ruff check --fix .

# --- Image builds ---------------------------------------------------------
# Build + push deployment images. The frontend build picks up
# `frontend/.env.<mode>` (gitignored — supply your own) via Vite's --mode.
# Override the image repo by setting BACKEND_IMAGE / FRONTEND_IMAGE in the
# environment. The default repo matches the existing CG stage publishing
# convention; replace it for your own deploy.

BACKEND_IMAGE  ?= docker.io/clinicalgenomics/metavis-backend
FRONTEND_IMAGE ?= docker.io/clinicalgenomics/metavis-frontend
PLATFORM       ?= linux/amd64

image-backend-stage:
	docker buildx build --platform $(PLATFORM) -f backend/Dockerfile.prod \
	  -t $(BACKEND_IMAGE):stage ./backend --push

image-frontend-stage:
	docker buildx build --platform $(PLATFORM) -f frontend/Dockerfile.prod \
	  --build-arg VITE_MODE=stage \
	  -t $(FRONTEND_IMAGE):stage ./frontend --push

image-backend-prod:
	docker buildx build --platform $(PLATFORM) -f backend/Dockerfile.prod \
	  -t $(BACKEND_IMAGE):prod ./backend --push

image-frontend-prod:
	docker buildx build --platform $(PLATFORM) -f frontend/Dockerfile.prod \
	  --build-arg VITE_MODE=prod \
	  -t $(FRONTEND_IMAGE):prod ./frontend --push