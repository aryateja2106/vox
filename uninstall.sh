#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "  Uninstalling vox..."
echo ""

REMOVED=0

if command -v pipx &>/dev/null; then
    pipx uninstall vox-shell 2>/dev/null && REMOVED=1 || true
fi

if command -v uv &>/dev/null && [ "$REMOVED" -eq 0 ]; then
    uv tool uninstall vox-shell 2>/dev/null && REMOVED=1 || true
fi

if [ "$REMOVED" -eq 0 ]; then
    python3 -m pip uninstall -y vox-shell 2>/dev/null && REMOVED=1 || true
fi

if [ "$REMOVED" -eq 1 ]; then
    echo "  ✓ vox uninstalled."
else
    echo "  vox was not found or already uninstalled."
fi
echo ""
