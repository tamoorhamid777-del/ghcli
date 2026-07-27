# Changelog

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
