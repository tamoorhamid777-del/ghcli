# ghcli — GitHub CLI Client

> Manage GitHub repositories, issues, pull requests, commits, and files directly from your terminal.

[![CI](https://github.com/tamoorhamid777-del/ghcli/actions/workflows/ci.yml/badge.svg)](https://github.com/tamoorhamid777-del/ghcli/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

```
  ██████╗ ██╗  ██╗ ██████╗██╗     ██╗
 ██╔════╝ ██║  ██║██╔════╝██║     ██║
 ██║  ███╗███████║██║     ██║     ██║
 ██║   ██║██╔══██║██║     ██║     ██║
 ╚██████╔╝██║  ██║╚██████╗███████╗██║
  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚══════╝╚═╝
```

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Authentication](#authentication)
- [Command Reference](#command-reference)
  - [auth](#auth)
  - [repos](#repos)
  - [issues](#issues)
  - [prs](#prs)
  - [commits](#commits)
  - [files](#files)
- [Environment Variables](#environment-variables)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Feature | Commands |
|---------|----------|
| 🔐 Authentication | `auth setup`, `auth status`, `auth logout` |
| 📦 Repositories | `repos list`, `repos view`, `repos create`, `repos delete`, `repos clone`, `repos fork` |
| 🐛 Issues | `issues list`, `issues view`, `issues create`, `issues close`, `issues reopen`, `issues comment` |
| 🔀 Pull Requests | `prs list`, `prs view`, `prs create`, `prs merge`, `prs close` |
| 📜 Commits | `commits list`, `commits view`, `commits compare` |
| 📁 Files | `files list`, `files view`, `files write`, `files delete`, `files tree` |

**Built with:**
- [Click](https://click.palletsprojects.com/) — CLI framework
- [Rich](https://rich.readthedocs.io/) — Beautiful terminal output
- [Requests](https://requests.readthedocs.io/) — HTTP client
- [Keyring](https://keyring.readthedocs.io/) — Secure token storage

---

## Requirements

- Python **3.10** or higher
- `git` installed on your system (for `repos clone`)
- A GitHub account with a [Personal Access Token](#authentication)

---

## Installation

### From source (recommended for development)

```bash
git clone https://github.com/tamoorhamid777-del/ghcli.git
cd ghcli
pip install -e .
```

### From PyPI (once published)

```bash
pip install ghcli
```

### With pipx (isolated install)

```bash
pipx install ghcli
```

Verify the installation:

```bash
ghcli --version
ghcli --help
```

---

## Authentication

ghcli uses a **GitHub Personal Access Token (PAT)** for authentication.

### Step 1 — Create a token

1. Go to **https://github.com/settings/tokens**
2. Click **"Generate new token (classic)"**
3. Give it a name (e.g. `ghcli`)
4. Select scopes:
   - `repo` — full repository access
   - `read:user` — read your profile
   - `read:org` — read organization data
   - `workflow` — manage GitHub Actions (optional)
5. Click **"Generate token"** and copy it

### Step 2 — Configure ghcli

```bash
ghcli auth setup
# Paste your token when prompted (input is hidden)
```

Or pass it directly:

```bash
ghcli auth setup --token ghp_xxxxxxxxxxxx
```

### Check status

```bash
ghcli auth status
```

### Log out

```bash
ghcli auth logout
```

> **Token storage:** ghcli stores your token in the OS keyring (macOS Keychain, Windows Credential Manager, or libsecret on Linux). If keyring is unavailable, it falls back to `~/.ghcli/config.json` (mode 600).

---

## Command Reference

### auth

Manage GitHub authentication.

```bash
ghcli auth setup              # Interactive token setup
ghcli auth setup -t TOKEN     # Non-interactive (for scripts)
ghcli auth status             # Show current user info
ghcli auth logout             # Remove stored token
ghcli auth logout --yes       # Skip confirmation
```

---

### repos

Manage GitHub repositories.

#### List repositories

```bash
ghcli repos list                          # Your repos (default: updated sort)
ghcli repos list --user octocat           # Another user's repos
ghcli repos list --org github             # Organization repos
ghcli repos list --type private           # Filter by type
ghcli repos list --sort stars --limit 10  # Top 10 by stars
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--user`, `-u` | authenticated user | GitHub username |
| `--org`, `-o` | — | Organization name |
| `--type` | `all` | `all`, `owner`, `member`, `public`, `private`, `forks`, `sources` |
| `--sort` | `updated` | `created`, `updated`, `pushed`, `full_name` |
| `--limit`, `-n` | `30` | Max repos to show |

#### View a repository

```bash
ghcli repos view owner/repo
ghcli repos view myrepo          # Defaults to your username
```

#### Create a repository

```bash
ghcli repos create my-new-repo
ghcli repos create my-new-repo --private --description "My project"
ghcli repos create my-new-repo --gitignore Python --license mit
ghcli repos create my-new-repo --org my-org
```

#### Clone a repository

```bash
ghcli repos clone owner/repo
ghcli repos clone owner/repo --dest ./local-dir
ghcli repos clone owner/repo --ssh          # Use SSH URL
ghcli repos clone owner/repo --depth 1      # Shallow clone
```

#### Fork a repository

```bash
ghcli repos fork owner/repo
ghcli repos fork owner/repo --org my-org
```

#### Delete a repository

```bash
ghcli repos delete owner/repo
ghcli repos delete owner/repo --yes    # Skip confirmation
```

---

### issues

Manage GitHub issues.

#### List issues

```bash
ghcli issues list owner/repo
ghcli issues list owner/repo --state closed
ghcli issues list owner/repo --label bug --limit 50
ghcli issues list owner/repo --assignee octocat
ghcli issues list owner/repo --sort comments
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--state` | `open` | `open`, `closed`, `all` |
| `--label`, `-l` | — | Filter by label name |
| `--assignee`, `-a` | — | Filter by assignee username |
| `--limit`, `-n` | `20` | Max issues to show |
| `--sort` | `created` | `created`, `updated`, `comments` |

#### View an issue

```bash
ghcli issues view owner/repo 42
```

Shows the issue body, metadata, and all comments.

#### Create an issue

```bash
ghcli issues create owner/repo --title "Bug: something is broken"
ghcli issues create owner/repo \
  --title "Feature request" \
  --body "Please add X because Y" \
  --label enhancement \
  --label good-first-issue \
  --assignee octocat
```

#### Close an issue

```bash
ghcli issues close owner/repo 42
ghcli issues close owner/repo 42 --comment "Fixed in #45"
```

#### Reopen an issue

```bash
ghcli issues reopen owner/repo 42
```

#### Add a comment

```bash
ghcli issues comment owner/repo 42 --body "Thanks for the report!"
```

---

### prs

Manage GitHub pull requests.

#### List pull requests

```bash
ghcli prs list owner/repo
ghcli prs list owner/repo --state closed
ghcli prs list owner/repo --base main
ghcli prs list owner/repo --sort popularity
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--state` | `open` | `open`, `closed`, `all` |
| `--base`, `-b` | — | Filter by base branch |
| `--head`, `-H` | — | Filter by head branch (`user:branch`) |
| `--sort` | `created` | `created`, `updated`, `popularity`, `long-running` |
| `--limit`, `-n` | `20` | Max PRs to show |

#### View a pull request

```bash
ghcli prs view owner/repo 7
ghcli prs view owner/repo 7 --diff    # Show unified diff
```

Shows metadata, changed files, and reviews.

#### Create a pull request

```bash
ghcli prs create owner/repo \
  --title "Add new feature" \
  --head feature-branch \
  --base main

ghcli prs create owner/repo \
  --title "Fix critical bug" \
  --head fix/critical-bug \
  --base main \
  --body "This fixes #42" \
  --label bug \
  --reviewer octocat \
  --draft
```

#### Merge a pull request

```bash
ghcli prs merge owner/repo 7
ghcli prs merge owner/repo 7 --method squash
ghcli prs merge owner/repo 7 --method rebase --message "feat: add new feature"
```

**Merge methods:** `merge` (default), `squash`, `rebase`

#### Close a pull request

```bash
ghcli prs close owner/repo 7
```

---

### commits

View commit history.

#### List commits

```bash
ghcli commits list owner/repo
ghcli commits list owner/repo --branch develop
ghcli commits list owner/repo --author octocat
ghcli commits list owner/repo --path src/main.py
ghcli commits list owner/repo --since 2024-01-01 --until 2024-12-31
ghcli commits list owner/repo --limit 50
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--branch`, `-b` | repo default | Branch, tag, or SHA |
| `--author`, `-a` | — | GitHub login or email |
| `--path`, `-p` | — | Only commits touching this path |
| `--since`, `-s` | — | ISO 8601 date (e.g. `2024-01-01`) |
| `--until`, `-u` | — | ISO 8601 date (e.g. `2024-12-31`) |
| `--limit`, `-n` | `20` | Max commits to show |

#### View a commit

```bash
ghcli commits view owner/repo abc1234
ghcli commits view owner/repo abc1234def5678901234567890abcdef12345678
```

Shows full commit message, author, stats, and changed files.

#### Compare branches/commits

```bash
ghcli commits compare owner/repo main develop
ghcli commits compare owner/repo v1.0.0 v2.0.0
ghcli commits compare owner/repo abc1234 def5678
```

---

### files

View and manage files in a repository.

#### List files in a directory

```bash
ghcli files list owner/repo
ghcli files list owner/repo --path src/
ghcli files list owner/repo --path src/ --branch develop
```

#### View file contents

```bash
ghcli files view owner/repo README.md
ghcli files view owner/repo src/main.py --branch develop
ghcli files view owner/repo config.json --raw          # No syntax highlighting
ghcli files view owner/repo script.sh --save local.sh  # Save to disk
```

Supports syntax highlighting for 30+ languages (Python, JS, TS, Go, Rust, Java, etc.).

#### Create or update a file

```bash
# Create from string content
ghcli files write owner/repo path/to/file.txt \
  --message "Add new file" \
  --content "Hello, world!"

# Create from a local file
ghcli files write owner/repo path/to/script.py \
  --message "Add script" \
  --file ./local_script.py

# Update on a specific branch
ghcli files write owner/repo config.json \
  --message "Update config" \
  --content '{"key": "value"}' \
  --branch feature-branch
```

If the file already exists, its SHA is fetched automatically and the file is updated.

#### Delete a file

```bash
ghcli files delete owner/repo path/to/old-file.txt --message "Remove old file"
ghcli files delete owner/repo path/to/old-file.txt --message "Remove" --yes
```

#### Show the full file tree

```bash
ghcli files tree owner/repo
ghcli files tree owner/repo --branch develop
ghcli files tree owner/repo --no-recursive    # Top-level only
ghcli files tree owner/repo --limit 500
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub PAT — takes priority over stored token |
| `GH_TOKEN` | Alias for `GITHUB_TOKEN` (gh CLI compatibility) |

These are ideal for CI/CD pipelines:

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
ghcli repos list
```

---

## Development

```bash
# Clone and set up
git clone https://github.com/tamoorhamid777-del/ghcli.git
cd ghcli
python3 -m venv .venv && source .venv/bin/activate
make install-dev

# Run tests
make test

# Format code
make format

# Lint
make lint

# Type check
make type-check

# Security scan
make security-check

# Build distribution
make build
```

### Project Structure

```
ghcli/
├── ghcli/
│   ├── __init__.py          # Package version
│   ├── main.py              # CLI entry point (click groups)
│   ├── client.py            # GitHub REST API wrapper
│   ├── auth_store.py        # Secure token storage
│   └── commands/
│       ├── __init__.py
│       ├── auth.py          # auth setup/status/logout
│       ├── repos.py         # repos list/view/create/clone/fork/delete
│       ├── issues.py        # issues list/view/create/close/reopen/comment
│       ├── prs.py           # prs list/view/create/merge/close
│       ├── commits.py       # commits list/view/compare
│       └── files.py         # files list/view/write/delete/tree
├── tests/
│   ├── conftest.py
│   └── test_auth.py
├── .github/
│   ├── workflows/ci.yml
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE/
├── pyproject.toml
├── requirements.txt
├── Makefile
├── LICENSE
├── CONTRIBUTING.md
└── README.md
```

---


## v1.1.0 — New Commands

### 🔍 Search
```bash
ghcli search repos "python cli" --language python --sort stars --limit 20
ghcli search issues "memory leak" --limit 10
ghcli search users "tamoor" --limit 5
ghcli search code "def require_auth" --limit 10
```

### 📋 Gists
```bash
ghcli gist list
ghcli gist create hello.py "print('hello')" --description "My gist" --public
ghcli gist view <gist-id>
ghcli gist delete <gist-id>
```

### 🚀 Releases
```bash
ghcli release list owner/repo
ghcli release create owner/repo v1.2.0 --name "v1.2.0" --body "Release notes"
ghcli release view owner/repo v1.0.0
ghcli release download owner/repo v1.0.0
```

### 🏢 Organizations
```bash
ghcli org list
ghcli org members myorg
ghcli org repos myorg --sort stars
ghcli org view myorg
```

### 🔔 Notifications
```bash
ghcli notifications list
ghcli notifications list --all
ghcli notifications read <thread-id>
ghcli notifications read-all --yes
```

### ⭐ Stars
```bash
ghcli star list
ghcli star list --user torvalds
ghcli star add owner/repo
ghcli star remove owner/repo
ghcli star check owner/repo
```

### 📊 Status
```bash
ghcli status          # auth info + rate limits
ghcli status --json   # raw JSON output
ghcli version         # show version
```

### 🔧 Global Flags (all list commands)
```bash
--json    # output raw JSON for scripting
--limit N # max results (default 10-20)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

---

## License

[MIT](LICENSE) © ghcli contributors
