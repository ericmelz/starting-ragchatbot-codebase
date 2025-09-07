#!/bin/bash

# Run all quality checks
echo "=== CODE QUALITY CHECKS ==="

echo "1. Running black (check only)..."
uv run black --check backend/ main.py
BLACK_EXIT_CODE=$?

echo "2. Running isort (check only)..."
uv run isort --check-only backend/ main.py  
ISORT_EXIT_CODE=$?

echo "3. Running flake8..."
uv run flake8 backend/ main.py
FLAKE8_EXIT_CODE=$?

echo "4. Running mypy..."
uv run mypy backend/ main.py
MYPY_EXIT_CODE=$?

echo "5. Running tests..."
uv run pytest backend/tests/
PYTEST_EXIT_CODE=$?

echo "=== SUMMARY ==="
if [ $BLACK_EXIT_CODE -eq 0 ]; then
    echo "✅ Black: PASS"
else
    echo "❌ Black: FAIL (run ./scripts/format.sh to fix)"
fi

if [ $ISORT_EXIT_CODE -eq 0 ]; then
    echo "✅ Isort: PASS"
else
    echo "❌ Isort: FAIL (run ./scripts/format.sh to fix)"
fi

if [ $FLAKE8_EXIT_CODE -eq 0 ]; then
    echo "✅ Flake8: PASS"
else
    echo "❌ Flake8: FAIL"
fi

if [ $MYPY_EXIT_CODE -eq 0 ]; then
    echo "✅ MyPy: PASS"
else
    echo "❌ MyPy: FAIL"
fi

if [ $PYTEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Tests: PASS"
else
    echo "❌ Tests: FAIL"
fi

# Exit with error if any check failed
if [ $BLACK_EXIT_CODE -ne 0 ] || [ $ISORT_EXIT_CODE -ne 0 ] || [ $FLAKE8_EXIT_CODE -ne 0 ] || [ $MYPY_EXIT_CODE -ne 0 ] || [ $PYTEST_EXIT_CODE -ne 0 ]; then
    exit 1
fi

echo "🎉 All checks passed!"