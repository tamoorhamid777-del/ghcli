#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-command setup for ghcli (GitHub CLI)
#
# Usage:
#   chmod +x setup.sh && ./setup.sh
#
# What it does:
#   1. Checks Python 3.10+ is available
#   2. Creates a virtual environment (.venv)
#   3. Installs ghcli in editable mode (pip install -e .)
#   4. Runs the test suite
#   5. Prints a quick-start guide
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
cat <<'EOF'
   ██████╗ ██╗  ██╗ ██████╗██╗     ██╗
  ██╔════╝ ██║  ██║██╔════╝██║     ██║
  ██║  ███╗███████║██║     ██║     ██║
  ██║   ██║██╔══██║██║     ██║     ██║
  ╚██████╔╝██║  ██║╚██████╗███████╗██║
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚══════╝╚═╝
  GitHub CLI — Setup Script
EOF
echo -e "${RESET}"

# ── 1. Python version check ───────────────────────────────────────────────────
info "Checking Python version…"
PYTHON=$(command -v python3 || command -v python || error "Python not found. Install Python 3.10+")
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
    error "Python 3.10+ required (found $PY_VER). Please upgrade."
fi
success "Python $PY_VER found at $PYTHON"

# ── 2. Virtual environment ────────────────────────────────────────────────────
VENV_DIR=".venv"
if [[ -d "$VENV_DIR" ]]; then
    warn "Virtual environment already exists at $VENV_DIR — reusing."
else
    info "Creating virtual environment at $VENV_DIR…"
    "$PYTHON" -m venv "$VENV_DIR"
    success "Virtual environment created."
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
success "Virtual environment activated."

# ── 3. Install ghcli ─────────────────────────────────────────────────────────
info "Installing ghcli in editable mode (pip install -e .)…"
pip install --upgrade pip -q
pip install -e ".[dev]" -q 2>&1 | grep -v "^$" | grep -v "notice" || \
pip install -e . -q 2>&1 | grep -v "^$" | grep -v "notice"
success "ghcli installed."

# ── 4. Verify CLI entry point ─────────────────────────────────────────────────
info "Verifying CLI entry point…"
ghcli --version
success "ghcli entry point works."

# ── 5. Run tests ──────────────────────────────────────────────────────────────
if [[ -d "tests" ]]; then
    info "Running test suite…"
    if python -m pytest tests/ -q --no-header --tb=short 2>&1; then
        success "All tests passed."
    else
        warn "Some tests failed — check output above. ghcli is still installed."
    fi
else
    warn "No tests/ directory found — skipping tests."
fi

# ── 6. Git repo init (optional) ───────────────────────────────────────────────
if [[ ! -d ".git" ]]; then
    info "Initialising git repository…"
    git init -q
    git add .
    git commit -q -m "feat: initial ghcli project setup"
    success "Git repository initialised with initial commit."
else
    warn ".git already exists — skipping git init."
fi

# ── 7. Quick-start guide ──────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  ✅  ghcli is ready!${RESET}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "${BOLD}Quick Start:${RESET}"
echo ""
echo -e "  ${CYAN}1. Activate the virtual environment:${RESET}"
echo -e "     source .venv/bin/activate"
echo ""
echo -e "  ${CYAN}2. Set up your GitHub token:${RESET}"
echo -e "     ghcli auth setup"
echo -e "     ${YELLOW}(Get a token at: https://github.com/settings/tokens)${RESET}"
echo ""
echo -e "  ${CYAN}3. Start using ghcli:${RESET}"
echo -e "     ghcli repos list"
echo -e "     ghcli issues list OWNER/REPO"
echo -e "     ghcli prs list OWNER/REPO"
echo -e "     ghcli commits list OWNER/REPO"
echo -e "     ghcli files list OWNER/REPO"
echo ""
echo -e "  ${CYAN}4. Explore skill modules:${RESET}"
echo -e "     ghcli skills --help"
echo -e "     ghcli skills mcp --help"
echo -e "     ghcli skills browser --help"
echo -e "     ghcli skills debug --help"
echo -e "     ghcli skills research --help"
echo -e "     ghcli skills prd --help"
echo -e "     ghcli skills tdd --help"
echo -e "     ghcli skills dispatch --help"
echo ""
echo -e "  ${CYAN}5. Get help on any command:${RESET}"
echo -e "     ghcli --help"
echo -e "     ghcli repos --help"
echo ""
echo -e "${BOLD}Documentation:${RESET} See README.md for full usage guide."
echo ""
