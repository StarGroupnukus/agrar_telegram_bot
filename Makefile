.PHONY: build run stop logs shell clean help

help:
	@echo "Available commands:"
	@echo "  make build    - Build Docker image"
	@echo "  make run      - Run Docker container"
	@echo "  make stop     - Stop Docker container"
	@echo "  make logs     - Show container logs"
	@echo "  make shell    - Access container shell"
	@echo "  make clean    - Remove container and image"

build:
	docker-compose build

run:
	docker-compose up -d

stop:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec telegram-bot bash

clean:
	docker-compose down --rmi all