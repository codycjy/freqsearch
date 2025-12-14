# FreqSearch Python Agent Dockerfile
# Multi-stage build for minimal final image

# ============================================
# Stage 1: Build
# ============================================
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir build && \
    pip wheel --no-cache-dir --wheel-dir /wheels -e .

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 freqsearch && \
    useradd -u 1000 -g freqsearch -s /bin/bash -m freqsearch

WORKDIR /app

# Copy wheels and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

# Copy application code
COPY src/ /app/src/

# Create data directories
RUN mkdir -p /data/strategies && \
    chown -R freqsearch:freqsearch /data /app

# Switch to non-root user
USER freqsearch

# Set Python path
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import freqsearch; print('ok')" || exit 1

# Run
ENTRYPOINT ["python", "-m", "freqsearch.main"]
