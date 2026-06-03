"""
Extensions Flask — initialisées sans app pour éviter les imports circulaires.
Importez depuis ce fichier dans models.py et les routes.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail

db            = SQLAlchemy()
login_manager = LoginManager()
migrate       = Migrate()
mail          = Mail()
