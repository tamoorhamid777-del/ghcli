# Contributing to ghcli

Thank you for your interest in contributing! This document explains how to get
started, what we expect from contributors, and how to submit changes.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to uphold these standards.

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ghcli.git
   cd ghcli
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b feat/my-new-feature
   ```

---

## Development Setup

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install in editable mode with all dev dependencies
make install-dev
# or: pip install -e ".[dev]"
```

Verify the installation:
```bash
ghcli --version
ghcli --help
```

---

## Running Tests

```bash
# Run the full test suite
make test

# Run with coverage report
make test-cov

# Run a single test file
pytest tests/test_auth.py -v
```

---

## Code Style

We use **Black** for formatting, **isort** for import sorting, and **flake8** for linting.

```bash
# Auto-format everything
make format

# Check for lint errors
make lint

# Type-check with mypy
make type-check

# Security scan with bandit
make security-check
```

All CI checks must pass before a PR can be merged.

---

## Submitting a Pull Request

1. Ensure all tests pass: `make test`
2. Ensure code is formatted: `make format`
3. Ensure no lint errors: `make lint`
4. Update `CHANGELOG.md` under the `[Unreleased]` section.
5. Push your branch and open a PR against `main`.
6. Fill in the PR template completely.
7. A maintainer will review your PR within a few days.

### PR Guidelines

- **One feature / fix per PR** — keep changes focused.
- **Write tests** for new functionality.
- **Update docs** (README, docstrings) if you change behaviour.
- **Squash commits** before merging (or we will squash for you).

---

## Reporting Bugs

Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:

- Your OS and Python version
- The exact command you ran
- The full error output (with `--debug` if available)
- Steps to reproduce

---

## Requesting Features

Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md).
Describe the use case, not just the solution.
