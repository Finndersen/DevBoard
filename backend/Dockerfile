FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY devboard/ ./devboard/

# Install dependencies
RUN uv sync --frozen

# Create data directory for persistence
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "uvicorn", "devboard.main:app", "--host", "0.0.0.0", "--port", "8000"]