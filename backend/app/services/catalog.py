"""Static reference data loaded once from seed_data.json (labels, spaces).

These are presentation constants (label -> color, the two spaces) rather than
mutable rows, so we read them straight from the seed file and cache them.
"""
from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings


@lru_cache
def _raw() -> dict:
    with settings.seed_data_path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def label_colors() -> dict[str, str]:
    return dict(_raw().get("labels", {}))


def label_color(name: str) -> str:
    # Fall back to a neutral token-ish grey for unknown labels.
    return label_colors().get(name, "#9A998F")


@lru_cache
def spaces() -> list[dict]:
    return list(_raw().get("spaces", []))


@lru_cache
def current_user_initials() -> str:
    return _raw().get("currentUser", "AL")
