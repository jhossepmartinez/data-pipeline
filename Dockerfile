FROM python:3.12-slim

WORKDIR /app

# Install dependencies from pyproject.toml
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application source
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create mount point for northwind.db (volume will override at runtime)
RUN mkdir -p /app/data/raw

# Default entrypoint runs the pipeline
CMD ["python", "-m", "src.main"]
