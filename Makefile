.PHONY: build up down logs restart clean

default: up

# Build the Docker images
build:
	docker compose -f docker-compose.yaml build  

# Run the Docker containers
up:
	docker compose -f docker-compose.yaml up -d

# Stop and remove the Docker containers
down:
	docker compose -f docker-compose.yaml down

logs:
	docker compose -f docker-compose.yaml logs -f

restart: down up

# Clean up Docker containers, images, and volumes
clean: down
	docker compose -f docker-compose.yaml rm -f
	docker system prune -f