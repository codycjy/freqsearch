.PHONY: all build run test clean proto lint fmt help

# Build variables
BINARY_NAME=freqsearch-backend
BUILD_DIR=./bin
MAIN_PATH=./cmd/server

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GORUN=$(GOCMD) run
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOMOD=$(GOCMD) mod
GOFMT=gofmt

# Versioning
VERSION?=$(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_TIME=$(shell date -u '+%Y-%m-%d_%H:%M:%S')
LDFLAGS=-ldflags "-X main.Version=$(VERSION) -X main.BuildTime=$(BUILD_TIME)"

all: build

## build: Build the binary
build:
	@echo "Building $(BINARY_NAME)..."
	@mkdir -p $(BUILD_DIR)
	$(GOBUILD) $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME) $(MAIN_PATH)

## run: Run the application
run:
	$(GORUN) $(MAIN_PATH)/main.go

## test: Run tests
test:
	$(GOTEST) -v -race -cover ./...

## test-coverage: Run tests with coverage report
test-coverage:
	$(GOTEST) -v -race -coverprofile=coverage.out ./...
	$(GOCMD) tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

## clean: Clean build artifacts
clean:
	@echo "Cleaning..."
	@rm -rf $(BUILD_DIR)
	@rm -f coverage.out coverage.html

## proto: Generate protobuf code
proto:
	@echo "Generating protobuf code..."
	@../scripts/generate_proto.sh

## lint: Run linter
lint:
	@echo "Running linter..."
	@golangci-lint run ./...

## fmt: Format code
fmt:
	@echo "Formatting code..."
	$(GOFMT) -s -w .

## deps: Download dependencies
deps:
	@echo "Downloading dependencies..."
	$(GOMOD) download
	$(GOMOD) tidy

## deps-update: Update dependencies
deps-update:
	$(GOMOD) tidy
	$(GOGET) -u ./...

## docker-build: Build Docker image
docker-build:
	docker build -t freqsearch-backend:$(VERSION) -f ../docker/go-backend/Dockerfile .

## migrate-up: Run database migrations
migrate-up:
	@echo "Running migrations..."
	@psql "$(DATABASE_URL)" -f ./internal/db/migrations/001_init_schema.up.sql

## migrate-down: Rollback database migrations
migrate-down:
	@echo "Rolling back migrations..."
	@psql "$(DATABASE_URL)" -f ./internal/db/migrations/001_init_schema.down.sql

## install-tools: Install development tools
install-tools:
	@echo "Installing development tools..."
	go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

## help: Show this help message
help:
	@echo "FreqSearch Go Backend - Available commands:"
	@echo ""
	@sed -n 's/^##//p' $(MAKEFILE_LIST) | column -t -s ':' | sed -e 's/^/ /'

# Default target
.DEFAULT_GOAL := help
