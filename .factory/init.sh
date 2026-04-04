#!/bin/bash
set -e

cd /Users/aryateja/Projects/vox

# Install dependencies (idempotent)
uv sync

# Verify baseline
uv run pytest tests/ -v --tb=short
uv run ruff check src/
