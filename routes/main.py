"""
Routes principales — ConstructLearn Pro
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Course, Enrollment, Payment

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    courses = Course.query.filter_by(published=True).order_by(Course.order_num).limit(6).all()
    return render_template("main/index.html", courses=courses)


@main_bp.route("/tableau-de-bord")
@login_required
def dashboard():
    enrollments = (
        Enrollment.query
        .filter_by(user_id=current_user.id)
        .join(Course)
        .filter(Course.published == True)
        .all()
    )
    # Formations disponibles selon le plan
    if current_user.is_pro or current_user.is_admin:
        available = Course.query.filter_by(published=True).order_by(Course.order_num).all()
    else:
        available = Course.query.filter_by(published=True, plan_required="free").order_by(Course.order_num).all()

    enrolled_ids = {e.course_id for e in enrollments}
    return render_template(
        "main/dashboard.html",
        enrollments=enrollments,
        available=available,
        enrolled_ids=enrolled_ids,
    )


@main_bp.route("/profil", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", "").strip() or current_user.first_name
        current_user.last_name  = request.form.get("last_name",  "").strip() or current_user.last_name
        new_pw  = request.form.get("new_password", "")
        curr_pw = request.form.get("current_password", "")
        if new_pw:
            if not current_user.check_password(curr_pw):
                flash("Mot de passe actuel incorrect.", "error")
                return redirect(url_for("main.profile"))
            if len(new_pw) < 8:
                flash("Le nouveau mot de passe doit faire au moins 8 caractères.", "error")
                return redirect(url_for("main.profile"))
            current_user.set_password(new_pw)
        db.session.commit()
        flash("Profil mis à jour.", "success")
        return redirect(url_for("main.profile"))
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).all()
    return render_template("main/profile.html", payments=payments)
