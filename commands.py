"""
Commandes CLI Flask — ConstructLearn Pro
Usage :
  flask init-db          → créer les tables
  flask create-admin     → créer le compte admin
  flask seed             → insérer des données de démo
"""
import click
from flask import current_app
from extensions import db


def register_commands(app):

    @app.cli.command("init-db")
    def init_db():
        """Crée toutes les tables en base."""
        db.create_all()
        click.echo("✅ Tables créées.")

    @app.cli.command("create-admin")
    @click.option("--email",    prompt="Email admin")
    @click.option("--password", prompt="Mot de passe", hide_input=True, confirmation_prompt=True)
    @click.option("--first",    prompt="Prénom", default="Admin")
    @click.option("--last",     prompt="Nom",    default="ConstructLearn")
    def create_admin(email, password, first, last):
        """Crée un compte administrateur."""
        from models import User
        if User.query.filter_by(email=email).first():
            click.echo("⚠️  Un utilisateur avec cet email existe déjà.")
            return
        user = User(email=email, first_name=first, last_name=last, role="admin",
                    plan="monthly", plan_status="active")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"✅ Admin créé : {email}")

    @app.cli.command("seed")
    def seed():
        """Insère des données de démonstration."""
        from models import Course, Video, User
        from utils import slugify

        # Formations
        demo_courses = [
            {"title": "Mécanique des sols — Fondamentaux",
             "category": "geo", "emoji": "🪨",
             "description": "Contraintes effectives, consolidation, cisaillement.",
             "duration": "8h30", "plan_required": "monthly", "published": True},
            {"title": "BIM & Revit — Modélisation géotechnique",
             "category": "bim", "emoji": "🏗️",
             "description": "Intégration des données géotechniques dans Revit et Civil 3D.",
             "duration": "6h00", "plan_required": "monthly", "published": True},
            {"title": "Fondations superficielles — Introduction",
             "category": "geo", "emoji": "🏛️",
             "description": "Semelles isolées, filantes. Calcul de capacité portante.",
             "duration": "3h00", "plan_required": "free", "published": True},
        ]
        for idx, c in enumerate(demo_courses):
            if not Course.query.filter_by(title=c["title"]).first():
                course = Course(order_num=idx, slug=slugify(c["title"]), **c)
                db.session.add(course)
                db.session.flush()
                # Ajouter 2 vidéos de démo
                for i, vtitle in enumerate([f"Leçon {i+1} — Introduction", f"Leçon {i+2} — Exercices pratiques"]):
                    v = Video(course_id=course.id, title=vtitle,
                              order_num=i, is_preview=(i == 0),
                              video_url="https://vimeo.com/example",
                              video_type="url", duration="45min")
                    db.session.add(v)

        # Utilisateur de démo
        if not User.query.filter_by(email="demo@constructlearn.pro").first():
            u = User(email="demo@constructlearn.pro",
                     first_name="Jean", last_name="Dupont",
                     plan="monthly", plan_status="active", role="member")
            u.set_password("Demo1234!")
            db.session.add(u)

        db.session.commit()
        click.echo("✅ Données de démo insérées.")
        click.echo("   📧 demo@constructlearn.pro / Demo1234!")
