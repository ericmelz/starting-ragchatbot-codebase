#!/bin/bash

# Run linting checks
echo "Running flake8..."
uv run flake8 backend/ main.py

echo "Running mypy..."
uv run mypy backend/ main.py

echo "Linting complete!"