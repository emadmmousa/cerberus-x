"""Effective ops flags: admin override → env → False."""

from __future__ import annotations

import os
from typing import Optional


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").lower() in {"1", "true", "yes", "on"}


def _resolve(override: Optional[bool], env_name: str) -> bool:
    if override is not None:
        return bool(override)
    return _env_truthy(env_name)


def effective_auto_scale() -> bool:
    from security.admin_store import auto_scale_override

    return _resolve(auto_scale_override(), "FIREBREAK_AUTO_SCALE")


def effective_auto_train() -> bool:
    from security.admin_store import auto_train_override

    return _resolve(auto_train_override(), "FIREBREAK_AUTO_TRAIN")


def effective_learning_tick() -> bool:
    from security.admin_store import learning_tick_override

    return _resolve(learning_tick_override(), "FIREBREAK_LEARNING_TICK")
