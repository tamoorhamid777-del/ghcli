# Security Policy

## Supported Versions

We actively maintain security fixes for the following versions of `ghcli`:

| Version | Supported |
|---------|-----------|
| 1.x.x   | ✅ Yes    |
| < 1.0   | ❌ No     |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in `ghcli`, please report it responsibly:

### Option 1: GitHub Private Security Advisory (Preferred)

1. Go to the [Security tab](https://github.com/your-org/ghcli/security) of this repository
2. Click **"Report a vulnerability"**
3. Fill in the details of the vulnerability

### Option 2: Email

Send an email to **security@ghcli.example.com** with:

- Subject: `[SECURITY] ghcli vulnerability report`
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

### What to Expect

- **Acknowledgement:** We will acknowledge receipt within **48 hours**
- **Assessment:** We will assess the severity and impact within **7 days**
- **Fix timeline:** Critical vulnerabilities will be patched within **14 days**; others within **30 days**
- **Disclosure:** We will coordinate public disclosure with you after a fix is available

We follow [responsible disclosure](https://en.wikipedia.org/wiki/Responsible_disclosure) principles and will credit you in the release notes (unless you prefer to remain anonymous).

## Security Considerations

### Token Storage

`ghcli` stores your GitHub Personal Access Token using your operating system's native
credential store (macOS Keychain, Windows Credential Manager, Linux Secret Service via
the `keyring` library). Tokens are **never** written to disk in plain text.

### Environment Variables

If you use the `GITHUB_TOKEN` environment variable, ensure it is not exposed in:
- Shell history files (`.bash_history`, `.zsh_history`)
- CI/CD logs (use masked secrets)
- Version control (never commit `.env` files)

### Minimal Scopes

We recommend creating a GitHub token with the **minimum required scopes**:
- `repo` — for repository operations
- `read:user` — for authentication status
- `read:org` — for organization repository listing

Avoid using tokens with `admin:org`, `delete_repo`, or other destructive scopes unless
you specifically need those features.

### Network Security

All API calls are made over HTTPS to `api.github.com`. We do not support HTTP or
unverified TLS connections.

## Known Security Considerations

- `ghcli` does not implement rate-limit backoff by default; excessive use may trigger
  GitHub's abuse detection
- The `files create/update/delete` commands make irreversible changes to repositories;
  use with care in automated scripts
