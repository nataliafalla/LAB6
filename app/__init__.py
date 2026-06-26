import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-prod")

    # MySQL RDS connection string
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

    db.init_app(app)
    login_manager.init_app(app)

    from .models import Admin

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Admin, int(user_id))

    from .auth import auth_bp
    from .routes import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)

    with app.app_context():
        db.create_all()
        # Seed default admin if none exists
        from werkzeug.security import generate_password_hash
        if not Admin.query.first():
            default = Admin(
                username=os.getenv("ADMIN_USER", "admin"),
                password_hash=generate_password_hash(
                    os.getenv("ADMIN_PASSWORD", "Admin123!")
                ),
            )
            db.session.add(default)
            db.session.commit()

    return app
