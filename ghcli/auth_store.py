"""
Secure token storage using OS keyring with a plaintext fallback.

Priority order for loading a token:
  1. GITHUB_TOKEN environment variable  (CI / Docker / devcontainer)
  2. GH_TOKEN environment variable      (gh CLI compat)
  3. OS keyring (macOS Keychain, Windows Credential Manager, libsecret)
  4. ~/.ghcli/config.json               (plaintext fallback, chmod 600)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".ghcli"
CONFIG_FILE = CONFIG_DIR / "config.json"
SERVICE_NAME = "ghcli"
ACCOUNT_NAME = "github_token"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _try_keyring():
    """Return the keyring module if available and functional, else None."""
    try:
        import keyring

        # Verify keyring actually works (some headless envs raise RuntimeError)
        keyring.get_keyring()
        return keyring
    except Exception:
        return None


def _read_config() -> dict:
    """Read ~/.ghcli/config.json; return empty dict on any error."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_config(data: dict) -> None:
    """Write ~/.ghcli/config.json with mode 600."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    CONFIG_FILE.chmod(0o600)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_token(token: str) -> str:
    """
    Persist the GitHub PAT.

    Tries OS keyring first; falls back to ~/.ghcli/config.json (mode 600).
    Returns ``"keyring"`` or ``"file"`` to indicate which backend was used.
    """
    kr = _try_keyring()
    if kr:
        try:
            kr.set_password(SERVICE_NAME, ACCOUNT_NAME, token)
            _write_config({"backend": "keyring", "version": 1})
            return "keyring"
        except Exception:
            pass  # fall through to file backend

    _write_config({"backend": "file", "token": token, "version": 1})
    return "file"


def load_token() -> str | None:
    """
    Load the stored GitHub PAT.

    Returns ``None`` if no token is configured anywhere.
    """
    # 1. Environment variables (highest priority — CI / Docker friendly)
    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env_token:
        return env_token.strip()

    cfg = _read_config()
    if not cfg:
        return None

    backend = cfg.get("backend")

    if backend == "keyring":
        kr = _try_keyring()
        if kr:
            try:
                token = kr.get_password(SERVICE_NAME, ACCOUNT_NAME)
                return token.strip() if token else None
            except Exception:
                pass
        # Keyring unavailable — token is lost; caller should re-run auth setup
        return None

    if backend == "file":
        token = cfg.get("token")
        return token.strip() if token else None

    return None


def delete_token() -> bool:
    """
    Remove the stored token from all backends.

    Returns ``True`` if something was actually deleted.
    """
    deleted = False

    # Try keyring
    kr = _try_keyring()
    if kr:
        try:
            kr.delete_password(SERVICE_NAME, ACCOUNT_NAME)
            deleted = True
        except Exception:
            pass

    # Remove config file regardless of backend
    if CONFIG_FILE.exists():
        try:
            CONFIG_FILE.unlink()
            deleted = True
        except OSError:
            pass

    return deleted


def token_is_set() -> bool:
    """Return True if a token is available from any source."""
    return load_token() is not None
