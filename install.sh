#!/usr/bin/env bash
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

echo ""
echo -e "  ${CYAN}${BOLD}vox${NC} — Talk to your terminal"
echo -e "  ${DIM}Natural language to shell commands, powered by a local AI model.${NC}"
echo ""

# ── Check Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "  ${RED}Error: Python 3 is required.${NC}"
    echo "  Install from https://python.org or your package manager."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    echo -e "  ${RED}Error: Python 3.9+ required (found $PY_VERSION)${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python $PY_VERSION"

# ── Install vox ──────────────────────────────────────────────────────────────
REPO="https://github.com/aryateja2106/vox.git"

if command -v pipx &>/dev/null; then
    echo -e "  ${DIM}Installing with pipx...${NC}"
    pipx install "git+${REPO}" --force 2>/dev/null && INSTALLED=1 || INSTALLED=0
elif command -v uv &>/dev/null; then
    echo -e "  ${DIM}Installing with uv...${NC}"
    uv tool install "git+${REPO}" --force 2>/dev/null && INSTALLED=1 || INSTALLED=0
else
    echo -e "  ${DIM}Installing with pip...${NC}"
    python3 -m pip install --user "git+${REPO}" --quiet 2>/dev/null && INSTALLED=1 || INSTALLED=0
fi

if [ "${INSTALLED:-0}" -eq 1 ]; then
    echo -e "  ${GREEN}✓${NC} vox installed"
else
    echo -e "  ${RED}✗${NC} Installation failed. Try manually:"
    echo "    pip install git+${REPO}"
    exit 1
fi

# ── Check Ollama ─────────────────────────────────────────────────────────────
echo ""
if command -v ollama &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Ollama detected"

    # Try to pull the nl2shell model
    if ollama list 2>/dev/null | grep -q "nl2shell"; then
        echo -e "  ${GREEN}✓${NC} nl2shell model ready"
    else
        echo -e "  ${YELLOW}!${NC} nl2shell model not found locally"
        echo -e "  ${DIM}  When available, pull with: ollama pull nl2shell${NC}"
        echo -e "  ${DIM}  For now, use any model: vox --model llama3.2${NC}"
    fi
else
    echo -e "  ${YELLOW}!${NC} Ollama not found"
    echo -e "  ${DIM}  Install from: https://ollama.ai${NC}"
    echo -e "  ${DIM}  Vox uses Ollama to run models locally — no cloud, no API keys.${NC}"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}${BOLD}Ready!${NC} Try it:"
echo ""
echo -e "    ${CYAN}vox${NC}                          ${DIM}# Interactive mode${NC}"
echo -e "    ${CYAN}vox${NC} \"find all python files\"   ${DIM}# Single command${NC}"
echo -e "    ${CYAN}vox${NC} --help                    ${DIM}# All options${NC}"
echo ""
