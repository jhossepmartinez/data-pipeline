#!/bin/sh
set -e

# Run Alembic migrations before any command
alembic upgrade head

# Execute the passed command, or default to running the pipeline
if [ $# -eq 0 ]; then
    exec python -m src.main
else
    exec "$@"
fi
