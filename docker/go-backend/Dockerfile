# FreqSearch Go Backend Dockerfile
# Multi-stage build for minimal final image

# ============================================
# Stage 1: Build
# ============================================
FROM golang:1.22-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /build

# Copy go mod files first for better caching
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the binary
ARG VERSION=dev
ARG BUILD_TIME
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s -X main.Version=${VERSION} -X main.BuildTime=${BUILD_TIME}" \
    -o /build/freqsearch-backend \
    ./cmd/server

# ============================================
# Stage 2: Runtime
# ============================================
FROM alpine:3.20

# Install runtime dependencies
RUN apk add --no-cache \
    ca-certificates \
    tzdata \
    docker-cli

# Create non-root user
RUN addgroup -g 1000 freqsearch && \
    adduser -u 1000 -G freqsearch -s /bin/sh -D freqsearch

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/freqsearch-backend /app/freqsearch-backend

# Create data directories
RUN mkdir -p /data/market /data/strategies && \
    chown -R freqsearch:freqsearch /data

# Switch to non-root user (commented out for docker socket access)
# USER freqsearch

# Expose ports
EXPOSE 50051 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Run
ENTRYPOINT ["/app/freqsearch-backend"]
