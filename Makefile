.PHONY: help dev staging prod build clean logs stop

help:
	@echo "🚀 Certificate Manager - Docker Commands"
	@echo "======================================"
	@echo " make dev      - Start development environment"
	@echo " make staging  - Start staging environment"
	@echo " make prod     - Start production environment"
	@echo " make build    - Build Docker images"
	@echo " make clean    - Remove containers and volumes"
	@echo " make logs     - Show application logs"
	@echo " make stop     - Stop all containers"
	@echo ""

dev:
	@echo "🛠️  Starting DEV environment on port 5000..."
	@docker compose -f docker-compose.yml -f docker-compose.override/dev.yml up --build

staging:
	@echo "🧪 Starting STAGING environment on port 5001..."
	@docker compose -f docker-compose.yml -f docker-compose.override/staging.yml up --build

prod:
	@echo "🚀 Starting PROD environment on port 80..."
	@docker compose -f docker-compose.yml -f docker-compose.override/prod.yml up --build -d

build:
	@echo "🐳 Building Docker images..."
	@docker compose build

clean:
	@echo "🧹 Cleaning up containers and volumes..."
	@docker compose down -v
	@docker system prune -f
	@echo "✨ Cleaned!"

logs:
	@docker compose logs -f

stop:
	@docker compose down

# Commandes utiles
init-db:
	@echo "🗃️  Initializing database..."
	@docker compose exec app python init_db.py

shell:
	@echo "🐚 Opening shell in app container..."
	@docker compose exec app sh

# Pour déployer sur un serveur distant
deploy:
	@echo "🚀 Deploying to production..."
	@git push origin main
	@echo "Then on your server, run: make prod"
