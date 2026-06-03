"""
ConstructLearn Pro — Application Flask
Géotechnique · BIM · Travaux Publics
"""
import os
from flask import Flask
from dotenv import load_dotenv
from extensions import db, login_manager, migrate, mail

load_dotenv()


def create_app():
    app = Flask(__name__)

    # ── Configuration ───────────────────────────────────────
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # ── Base de données ─────────────────────────────────────
    database_url = os.environ.get("DATABASE_URL", "sqlite:///constructlearn.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"]        = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"]      = {
        "pool_pre_ping": True,
        "pool_recycle":  300,
    }

    # ── Upload ──────────────────────────────────────────────
    app.config["UPLOAD_FOLDER"]      = os.path.join(app.root_path, "static", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 Mo max

    # ── Mail ────────────────────────────────────────────────
    app.config["MAIL_SERVER"]         = os.environ.get("MAIL_SERVER",  "smtp.gmail.com")
    app.config["MAIL_PORT"]           = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"]        = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USERNAME"]       = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"]       = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@constructlearn.pro")

    # ── Stripe ──────────────────────────────────────────────
    app.config["STRIPE_PUBLISHABLE_KEY"] = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    app.config["STRIPE_SECRET_KEY"]      = os.environ.get("STRIPE_SECRET_KEY",      "")
    app.config["STRIPE_WEBHOOK_SECRET"]  = os.environ.get("STRIPE_WEBHOOK_SECRET",  "")
    app.config["STRIPE_PRICE_MONTHLY"]   = os.environ.get("STRIPE_PRICE_MONTHLY",   "")
    app.config["STRIPE_PRICE_ANNUAL"]    = os.environ.get("STRIPE_PRICE_ANNUAL",    "")
    app.config["APP_URL"]                = os.environ.get("APP_URL", "http://localhost:5000")

    # ── Init extensions ─────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view             = "auth.login"
    login_manager.login_message          = "Connectez-vous pour accéder à cette page."
    login_manager.login_message_category = "warning"

    # ── Blueprints ──────────────────────────────────────────
    from routes.main    import main_bp
    from routes.auth    import auth_bp
    from routes.courses import courses_bp
    from routes.billing import billing_bp
    from routes.admin   import admin_bp
    from routes.api     import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,    url_prefix="/auth")
    app.register_blueprint(courses_bp, url_prefix="/formations")
    app.register_blueprint(billing_bp, url_prefix="/abonnement")
    app.register_blueprint(admin_bp,   url_prefix="/admin")
    app.register_blueprint(api_bp,     url_prefix="/api")

    # ── Dossier uploads ─────────────────────────────────────
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ── Création automatique des tables au premier démarrage ─
    with app.app_context():
        try:
            import models  # noqa
            db.create_all()
        except Exception as e:
            app.logger.warning(f"db.create_all() ignoré : {e}")

    # ── Commandes CLI ───────────────────────────────────────
    from commands import register_commands
    register_commands(app)

    return app


# Point d'entrée Gunicorn
app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_ENV") != "production")
