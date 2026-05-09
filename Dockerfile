FROM python:3.12-slim

WORKDIR /app

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml .

# Install dependencies using uv (falls back to pip if needed)
RUN uv pip install --system -e ".[dev]"

# Copy application source
COPY src/ ./src/
COPY tests/ ./tests/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY data/raw/northwind.db.sha256 ./data/raw/northwind.db.sha256

# Create mount point for northwind.db (volume will override at runtime)
RUN mkdir -p /app/data/raw

# Copy and set up entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default entrypoint runs the pipeline
ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
