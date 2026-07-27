# Changelog

## [1.2.2] — 2026-07-28

### Fixed
- **`--json` empty-list bug** — `issues list`, `prs list`, `repos list`, `commits list` now correctly
  output `[]` (valid JSON) instead of a human-readable "No items found" message when the result set
  is empty and `--json` is passed. This was breaking any script or pipeline that piped the output
  through `jq` or `json.loads()`.
- **mypy CI failures** — resolved 8 type errors that were causing the `lint` CI job to fail on every
  push: unused `type: ignore` in `auth_store.py`, incompatible return type in `client.py`
  (`_CachedResp`), 5 `arg-type` errors in `skills/deep_research.py`, and a `None not callable`
  error in `skills/parallel_dispatch.py`.
- **black/isort formatting** — re-formatted all 8 files touched by the above fixes so `black --check`
  and `isort --check-only` pass cleanly in CI.

### Verified (deployment audit)
- Fresh clone → `pip install -e .` → `ghcli --version 1.2.2` works with zero friction
- All 16 command groups and 54 subcommands respond correctly
- 11/11 `--json` list commands output valid, parseable JSON
- `pytest 223/223` passed · coverage 79% · `ast.parse 29/29` clean
- `mypy` 0 errors · `black` clean · `isort` clean · `bandit -ll` 0 Medium/High issues

## [1.2.1] — 2026-07-27

### Added
- `ghcli completions generate/install` — Shell tab-completion for bash, zsh, and fish
- Pre-generated completion scripts in `completions/ghcli.bash`, `completions/ghcli.zsh`, `completions/ghcli.fish`
- PyPI Trusted Publishing workflow (`.github/workflows/release.yml`) — auto-publishes on `v*` tag push
- `pytest-cov` in dev dependencies; coverage reporting in CI (`--cov=ghcli --cov-report=xml`)
- Coverage badge in README (80% achieved)
- 136 new tests across 7 new test files (`test_status.py`, `test_commits.py`, `test_client.py`, `test_completions.py`, `test_files.py`, `test_prs.py`, `test_issues.py`)
- Total: **223 tests, 100% passing, 80% coverage**

### Changed
- Version bumped to `1.2.1`
- README updated with coverage badge, shell completion installation guide, and `completions/` directory reference

## [1.2.0] — 2026-07-27

### Added
- `ghcli comments create/list/delete` — Add and manage comments on issues and PRs
- `ghcli repos create` — Create new repositories with `--private`, `--gitignore`, `--license`, `--org` flags
- `ghcli repos delete` — Delete a repository with double-confirmation safety
- `ghcli repos fork` — Fork a repository to your account or an org (`--org`)
- `ghcli repos clone` — Clone a repo by shorthand with `--ssh` and `--depth` flags
- `ghcli issues create` — Create issues with `--title`, `--body`, `--label`, `--assignee`, `--milestone`
- `ghcli issues close` — Close an issue with optional `--comment`
- `ghcli issues reopen` — Reopen a closed issue
- `ghcli issues comment` — Add a comment to an issue
- `ghcli prs create` — Create PRs with `--title`, `--head`, `--base`, `--draft`, `--label`, `--reviewer`
- `ghcli prs merge` — Merge a PR with `--method` (merge/squash/rebase) and `--message`
- `ghcli prs close` — Close a PR without merging
- 46 new tests across 3 new test files (87 total, 100% passing)

### Changed
- Bumped version to 1.2.0
- `main.py` updated to register `comments` command group

## [1.1.0] — 2026-07-27

### Added
- `ghcli search repos/issues/code/users` — search GitHub with `--language`, `--sort`, `--limit`, `--json`
- `ghcli gist create/list/view/delete` — full Gist management
- `ghcli release list/create/view/download` — GitHub Releases management
- `ghcli org list/members/repos/view` — Organization management
- `ghcli notifications list/read/read-all` — Notification management
- `ghcli star add/remove/list/check` — Star management
- `ghcli status` — Auth status + API rate limit dashboard
- `ghcli version` — Show version
- `--json` output flag on all list commands for scripting
- `--limit` / `--page` pagination flags on all list commands
- Response caching with 30s TTL in `GitHubClient`
- Exponential backoff retry (3 attempts) for 429/5xx errors
- 41 tests across 8 test files (100% passing)

### Changed
- Bumped version to 1.1.0
- `client.py` upgraded with caching, retry, and pagination helpers


All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Nothing yet.

---

## [1.0.0] — 2024-07-27

### Added

#### Authentication (`ghcli auth`)
- `auth setup` — Interactive GitHub PAT setup with live token validation
- `auth status` — Show authenticated user profile (name, email, repos, followers)
- `auth logout` — Remove stored token with confirmation prompt
- OS keyring storage (macOS Keychain, Windows Credential Manager, libsecret)
- Plaintext fallback at `~/.ghcli/config.json` (mode 600)
- `GITHUB_TOKEN` / `GH_TOKEN` environment variable support (CI-friendly)

#### Repository Management (`ghcli repos`)
- `repos list` — List repos with visibility, stars, forks, language, updated date
- `repos view` — Detailed repo info (description, topics, license, URLs)
- `repos create` — Create repos with gitignore/license templates, org support
- `repos clone` — Clone via HTTPS or SSH with optional shallow depth
- `repos fork` — Fork into personal account or organization
- `repos delete` — Delete with confirmation guard

#### Issue Management (`ghcli issues`)
- `issues list` — List with state/label/assignee filters, PR entries excluded
- `issues view` — Full issue view with body (Markdown rendered) and all comments
- `issues create` — Create with labels, assignees, milestone
- `issues close` — Close with optional closing comment
- `issues reopen` — Reopen a closed issue
- `issues comment` — Add a comment to any issue

#### Pull Request Management (`ghcli prs`)
- `prs list` — List with state/base/head filters
- `prs view` — Full PR view: metadata, changed files table, reviews, optional unified diff
- `prs create` — Create with labels, assignees, reviewers, draft mode
- `prs merge` — Merge via `merge`, `squash`, or `rebase` method
- `prs close` — Close without merging

#### Commit History (`ghcli commits`)
- `commits list` — List with branch/author/path/date-range filters
- `commits view` — Full commit: message, stats, changed files table
- `commits compare` — Compare two refs (ahead/behind/total commits)

#### File Operations (`ghcli files`)
- `files list` — List directory contents with size and SHA
- `files view` — View file with syntax highlighting (30+ languages, Monokai theme)
- `files write` — Create or update files (auto-fetches SHA for updates)
- `files delete` — Delete files with commit message (uses correct DELETE+body API)
- `files tree` — Full recursive file tree via Git Trees API

#### Infrastructure
- `GitHubClient` — Thin `requests` wrapper with rate-limit handling, pagination, `delete_with_body`, `get_diff`
- Link-header pagination (follows `rel="next"` automatically)
- Rich terminal UI: colored tables, panels, syntax highlighting, state badges
- `pyproject.toml` with `[project.scripts]` entry point (`ghcli = "ghcli.main:main"`)
- `Makefile` with `install`, `install-dev`, `test`, `test-cov`, `lint`, `format`, `type-check`, `security-check`, `build`, `publish`
- GitHub Actions CI: lint + test matrix (3 OS × 3 Python versions) + security scan + build check
- Issue templates (bug report, feature request)
- PR template
- MIT License, CONTRIBUTING.md, CODE_OF_CONDUCT.md, .gitignore

### Fixed
- `files delete` — Replaced broken `AttributeError` fallback with proper `delete_with_body()` method
- `prs view --diff` — Replaced raw `requests` import with `client.get_diff()` helper
- `auth_store` — Fixed keyring availability check (headless environments no longer crash)
- `paginate()` — Now handles wrapped responses (`items`, `workflows`, `jobs` keys)

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| [1.0.0] | 2024-07-27 | Initial production release |

[Unreleased]: https://github.com/your-org/ghcli/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/your-org/ghcli/releases/tag/v1.0.0