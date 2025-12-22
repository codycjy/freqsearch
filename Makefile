.PHONY: all build build-frontend build-backend clean dev help

# Build variables
BINARY_NAME=freqsearch-backend
BUILD_DIR=./go-backend/bin
FRONTEND_DIR=./frontend
BACKEND_DIR=./go-backend
WEB_DIST_DIR=$(BACKEND_DIR)/web/dist

# Default target
.DEFAULT_GOAL := help

## all: Build frontend and backend
all: build

## build: Build frontend and backend with embedded files
build: build-frontend build-backend

## build-frontend: Build the frontend and copy to go-backend/web/dist
build-frontend:
	@echo "Building frontend..."
	@cd $(FRONTEND_DIR) && npm install && npm run build
	@echo "Copying frontend build to $(WEB_DIST_DIR)..."
	@rm -rf $(WEB_DIST_DIR)
	@mkdir -p $(WEB_DIST_DIR)
	@cp -r $(FRONTEND_DIR)/dist/* $(WEB_DIST_DIR)/
	@echo "Frontend build complete"

## build-backend: Build the Go backend with embedded frontend
build-backend:
	@echo "Building backend..."
	@cd $(BACKEND_DIR) && $(MAKE) build
	@echo "Backend build complete"

## clean: Clean all build artifacts
clean:
	@echo "Cleaning..."
	@rm -rf $(WEB_DIST_DIR)
	@cd $(BACKEND_DIR) && $(MAKE) clean
	@echo "Clean complete"

## dev-frontend: Run frontend dev server
dev-frontend:
	@cd $(FRONTEND_DIR) && npm run dev

## dev-backend: Run backend dev server
dev-backend:
	@cd $(BACKEND_DIR) && $(MAKE) run

## test: Run all tests
test:
	@cd $(BACKEND_DIR) && $(MAKE) test

## lint: Run linters
lint:
	@cd $(FRONTEND_DIR) && npm run lint
	@cd $(BACKEND_DIR) && $(MAKE) lint

## deps: Install all dependencies
deps:
	@echo "Installing frontend dependencies..."
	@cd $(FRONTEND_DIR) && npm install
	@echo "Installing backend dependencies..."
	@cd $(BACKEND_DIR) && $(MAKE) deps

## proto: Generate protobuf code
proto:
	@cd $(BACKEND_DIR) && $(MAKE) proto

## docker-build: Build Docker image
docker-build: build
	@cd $(BACKEND_DIR) && $(MAKE) docker-build

## help: Show this help message
help:
	@echo "FreqSearch - Available commands:"
	@echo ""
	@sed -n 's/^##//p' $(MAKEFILE_LIST) | column -t -s ':' | sed -e 's/^/ /'
