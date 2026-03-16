from __future__ import annotations

from app.core.config import settings  # noqa: F401 — make settings importable from core

from app.core.config import settings as _settings

# Re-export commonly used items
__all__ = ["settings"]
