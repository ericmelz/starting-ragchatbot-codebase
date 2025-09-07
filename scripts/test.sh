#!/bin/bash

# Run tests with coverage
echo "Running tests..."
uv run pytest backend/tests/ -v --tb=short

echo "Tests complete!"