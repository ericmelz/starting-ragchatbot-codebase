#!/bin/bash

# Format code with black and isort
echo "Running black..."
uv run black backend/ main.py

echo "Running isort..."
uv run isort backend/ main.py

echo "Code formatting complete!"