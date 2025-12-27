# Custom Freqtrade image with additional libraries for strategy validation
FROM freqtradeorg/freqtrade:2025.4_freqai

# Switch to root to install packages and set permissions
USER root

# Install additional indicator libraries
RUN pip install --no-cache-dir \
    technical \
    pandas-ta

# Create validation script with proper permissions
COPY --chmod=755 validate_strategy.py /opt/validate_strategy.py

# Verify installation
RUN python -c "from technical.indicators import cmf, laguerre; print('technical OK')" && \
    python -c "import pandas_ta; print('pandas_ta OK')"

# Switch back to freqtrade user for security
USER ftuser

# Default command for validation mode
ENTRYPOINT ["python", "/opt/validate_strategy.py"]
