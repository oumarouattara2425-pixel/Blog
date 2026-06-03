"""
Routes d'authentification — ConstructLearn Pro
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/connexion", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            from datetime import datetime, timezone
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=remember)
            next_page = request.args.get("next")
            if user.is_admin:
                return redirect(next_page or url_for("admin.dashboard"))
            return redirect(next_page or url_for("main.dashboard"))
        flash("Email ou mot de passe incorrect.", "error")
    return render_template("auth/login.html")


@auth_bp.route("/inscription", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name  = request.form.get("last_name",  "").strip()
        email      = request.form.get("email", "").strip().lower()
        password   = request.form.get("password", "")
        if not all([first_name, last_name, email, password]):
            flash("Tous les champs sont obligatoires.", "error")
            return render_template("auth/register.html")
        if len(password) < 8:
            flash("Le mot de passe doit faire au moins 8 caractères.", "error")
            return render_template("auth/register.html")
        if User.query.filter_by(email=email).first():
            flash("Cette adresse email est déjà utilisée.", "error")
            return render_template("auth/register.html")
        user = User(first_name=first_name, last_name=last_name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"Bienvenue, {first_name} ! Votre compte est créé.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html")


@auth_bp.route("/deconnexion")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("main.index"))
