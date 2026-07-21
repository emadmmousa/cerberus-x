"""Mission Control API blueprints (controllers)."""

from __future__ import annotations

from flask import Flask


def register_api_blueprints(app: Flask) -> None:
    from orchestrator.api.admin import admin_bp
    from orchestrator.api.ai import ai_bp
    from orchestrator.api.blackboard import blackboard_bp
    from orchestrator.api.catalog import catalog_bp
    from orchestrator.api.chat_missions import chat_missions_bp
    from orchestrator.api.dataset import dataset_bp
    from orchestrator.api.edition import edition_bp
    from orchestrator.api.missions import missions_bp
    from orchestrator.api.proxy import proxy_bp
    from orchestrator.api.results import results_bp
    from orchestrator.api.scaffolds import scaffolds_bp
    from orchestrator.api.session import session_bp

    app.register_blueprint(session_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(missions_bp)
    app.register_blueprint(chat_missions_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(blackboard_bp)
    app.register_blueprint(dataset_bp)
    app.register_blueprint(scaffolds_bp)
    app.register_blueprint(edition_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(proxy_bp)
    app.register_blueprint(catalog_bp)
