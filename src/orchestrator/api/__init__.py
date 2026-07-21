"""Mission Control API blueprints (controllers)."""

from __future__ import annotations

from flask import Flask


def register_api_blueprints(app: Flask) -> None:
    from orchestrator.api.admin import admin_bp

    app.register_blueprint(admin_bp)
