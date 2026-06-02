from __future__ import annotations
from flask import Flask
from .config import get_config
from . import db as dbmod


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    app.teardown_appcontext(dbmod.close_db)

    with app.app_context():
        dbmod.init_db_if_needed()

    from .blueprints.main import bp as main_bp
    from .blueprints.kampagne import bp as kampagne_bp
    from .blueprints.sektor import bp as sektor_bp
    from .blueprints.nsc import bp as nsc_bp
    from .blueprints.auftrag import bp as auftrag_bp
    from .blueprints.fraktion import bp as fraktion_bp
    from .blueprints.welt import bp as welt_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(kampagne_bp)
    app.register_blueprint(sektor_bp)
    app.register_blueprint(nsc_bp)
    app.register_blueprint(auftrag_bp)
    app.register_blueprint(fraktion_bp)
    app.register_blueprint(welt_bp)

    return app
