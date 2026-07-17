"""Tiny environment helper: loads .env files once, exposes typed getters."""
import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _BACKEND_DIR.parent

# Precedence (12-factor): real OS environment > backend/.env > repo-root .env.
# override=False everywhere so container/CI env vars are never clobbered by files.
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_REPO_ROOT / ".env")


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def env_csv(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]
