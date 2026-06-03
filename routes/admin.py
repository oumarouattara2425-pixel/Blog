"""
Routes admin — ConstructLearn Pro
"""
import os
from datetime import datetime, timezone
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, jsonify)
from flask_login import login_required, current_user
from functools import wraps
from extensions import db
from models import Course, Video, User, Enrollment, Payment, PaymentSettings, VideoDocument
from utils import save_uploaded_file, slugify

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Accès réservé aux administrateurs.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════
@admin_bp.route("/")
@admin_required
def dashboard():
    stats = {
        "users":    User.query.count(),
        "courses":  Course.query.count(),
        "videos":   Video.query.count(),
        "pro":      User.query.filter(User.plan != "free").count(),
        "monthly":  User.query.filter_by(plan="monthly", plan_status="active").count(),
        "annual":   User.query.filter_by(plan="annual",  plan_status="active").count(),
        "revenue":  db.session.query(db.func.sum(Payment.amount_cents))
                      .filter_by(status="paid").scalar() or 0,
    }
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats,
                           recent_users=recent_users, recent_payments=recent_payments)


# ══════════════════════════════════════════════════════════
# FORMATIONS
# ══════════════════════════════════════════════════════════
@admin_bp.route("/formations")
@admin_required
def courses():
    courses = Course.query.order_by(Course.order_num, Course.created_at.desc()).all()
    return render_template("admin/courses.html", courses=courses)


@admin_bp.route("/formations/nouveau", methods=["GET", "POST"])
@admin_required
def course_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Le titre est obligatoire.", "error")
            return render_template("admin/course_form.html", course=None)

        course = Course(
            title=title,
            slug=slugify(title),
            description=request.form.get("description", "").strip(),
            category=request.form.get("category", "geo"),
            emoji=request.form.get("emoji", "🎓"),
            duration=request.form.get("duration", "").strip(),
            plan_required=request.form.get("plan_required", "monthly"),
            published=bool(request.form.get("published")),
        )
        # Vignette
        thumb = request.files.get("thumbnail")
        if thumb and thumb.filename:
            path = save_uploaded_file(thumb, subfolder="thumbnails")
            if path:
                course.thumbnail_url = url_for("static", filename=f"uploads/{path}")

        # Unicité du slug
        base_slug, counter = course.slug, 1
        while Course.query.filter_by(slug=course.slug).first():
            course.slug = f"{base_slug}-{counter}"; counter += 1

        db.session.add(course)
        db.session.commit()
        flash(f"Formation « {course.title} » créée.", "success")
        return redirect(url_for("admin.course_edit", course_id=course.id))
    return render_template("admin/course_form.html", course=None)


@admin_bp.route("/formations/<int:course_id>/modifier", methods=["GET", "POST"])
@admin_required
def course_edit(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        course.title        = request.form.get("title", course.title).strip()
        course.description  = request.form.get("description", "").strip()
        course.category     = request.form.get("category", course.category)
        course.emoji        = request.form.get("emoji", course.emoji)
        course.duration     = request.form.get("duration", "").strip()
        course.plan_required= request.form.get("plan_required", course.plan_required)
        course.published    = bool(request.form.get("published"))
        thumb = request.files.get("thumbnail")
        if thumb and thumb.filename:
            path = save_uploaded_file(thumb, subfolder="thumbnails")
            if path:
                course.thumbnail_url = url_for("static", filename=f"uploads/{path}")
        db.session.commit()
        flash("Formation mise à jour.", "success")
        return redirect(url_for("admin.course_edit", course_id=course.id))
    videos = course.videos.order_by(Video.order_num).all()
    return render_template("admin/course_form.html", course=course, videos=videos)


@admin_bp.route("/formations/<int:course_id>/supprimer", methods=["POST"])
@admin_required
def course_delete(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash(f"Formation « {course.title} » supprimée.", "success")
    return redirect(url_for("admin.courses"))


# ══════════════════════════════════════════════════════════
# VIDÉOS
# ══════════════════════════════════════════════════════════
@admin_bp.route("/formations/<int:course_id>/videos/nouveau", methods=["GET", "POST"])
@admin_required
def video_new(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        video = Video(
            course_id=course_id,
            title=request.form.get("title", "").strip(),
            description=request.form.get("description", "").strip(),
            duration=request.form.get("duration", "").strip(),
            order_num=int(request.form.get("order_num", 0)),
            is_preview=bool(request.form.get("is_preview")),
        )
        # Source vidéo
        video_file = request.files.get("video_file")
        video_url  = request.form.get("video_url", "").strip()
        if video_file and video_file.filename:
            path = save_uploaded_file(video_file, subfolder="videos", allowed=allowed_video)
            if path:
                video.video_file = path
                video.video_type = "upload"
        elif video_url:
            video.video_url  = video_url
            video.video_type = "url"

        db.session.add(video)
        db.session.flush()  # Pour avoir l'ID

        # Documents joints
        for doc_file in request.files.getlist("documents"):
            if doc_file and doc_file.filename:
                path = save_uploaded_file(doc_file, subfolder="docs", allowed=allowed_doc)
                if path:
                    doc = VideoDocument(
                        video_id=video.id,
                        filename=doc_file.filename,
                        file_path=path,
                        file_size=os.path.getsize(
                            os.path.join(current_app.config["UPLOAD_FOLDER"], path)
                        ),
                    )
                    db.session.add(doc)

        db.session.commit()
        flash(f"Vidéo « {video.title} » ajoutée.", "success")
        return redirect(url_for("admin.course_edit", course_id=course_id))
    last_order = course.videos.count()
    return render_template("admin/video_form.html", course=course, video=None, next_order=last_order)


@admin_bp.route("/videos/<int:video_id>/modifier", methods=["GET", "POST"])
@admin_required
def video_edit(video_id):
    video  = Video.query.get_or_404(video_id)
    course = video.course
    if request.method == "POST":
        video.title       = request.form.get("title", video.title).strip()
        video.description = request.form.get("description", "").strip()
        video.duration    = request.form.get("duration", "").strip()
        video.order_num   = int(request.form.get("order_num", video.order_num))
        video.is_preview  = bool(request.form.get("is_preview"))
        video_url = request.form.get("video_url", "").strip()
        if video_url:
            video.video_url  = video_url
            video.video_type = "url"
        new_file = request.files.get("video_file")
        if new_file and new_file.filename:
            path = save_uploaded_file(new_file, subfolder="videos", allowed=allowed_video)
            if path:
                video.video_file = path
                video.video_type = "upload"
        db.session.commit()
        flash("Vidéo mise à jour.", "success")
        return redirect(url_for("admin.course_edit", course_id=course.id))
    return render_template("admin/video_form.html", course=course, video=video)


@admin_bp.route("/videos/<int:video_id>/supprimer", methods=["POST"])
@admin_required
def video_delete(video_id):
    video = Video.query.get_or_404(video_id)
    course_id = video.course_id
    db.session.delete(video)
    db.session.commit()
    flash("Vidéo supprimée.", "success")
    return redirect(url_for("admin.course_edit", course_id=course_id))


# ══════════════════════════════════════════════════════════
# UTILISATEURS
# ══════════════════════════════════════════════════════════
@admin_bp.route("/utilisateurs")
@admin_required
def users():
    q    = request.args.get("q", "").strip()
    plan = request.args.get("plan", "all")
    query = User.query
    if q:
        query = query.filter(
            db.or_(User.email.ilike(f"%{q}%"),
                   User.first_name.ilike(f"%{q}%"),
                   User.last_name.ilike(f"%{q}%"))
        )
    if plan != "all":
        query = query.filter_by(plan=plan)
    users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users, q=q, plan=plan)


@admin_bp.route("/utilisateurs/<int:user_id>/modifier", methods=["POST"])
@admin_required
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    user.role = request.form.get("role", user.role)
    new_plan  = request.form.get("plan")
    if new_plan and new_plan != user.plan:
        user.plan = new_plan
        user.plan_status = "active" if new_plan != "free" else "inactive"
    db.session.commit()
    flash(f"Utilisateur {user.full_name} mis à jour.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/utilisateurs/<int:user_id>/supprimer", methods=["POST"])
@admin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
        return redirect(url_for("admin.users"))
    db.session.delete(user)
    db.session.commit()
    flash("Utilisateur supprimé.", "success")
    return redirect(url_for("admin.users"))


# ══════════════════════════════════════════════════════════
# ABONNEMENTS
# ══════════════════════════════════════════════════════════
@admin_bp.route("/abonnements")
@admin_required
def subscriptions():
    subs    = User.query.filter(User.plan != "free").order_by(User.created_at.desc()).all()
    payments= Payment.query.order_by(Payment.created_at.desc()).limit(50).all()
    ps      = PaymentSettings.query.first()
    monthly_price = (ps.monthly_price // 100) if ps else 29
    annual_price  = (ps.annual_price  // 100) if ps else 279
    nmo   = sum(1 for u in subs if u.plan == "monthly" and u.plan_status == "active")
    nan   = sum(1 for u in subs if u.plan == "annual"  and u.plan_status == "active")
    mrr   = nmo * monthly_price + nan * (annual_price // 12)
    arr   = nmo * monthly_price * 12 + nan * annual_price
    return render_template("admin/subscriptions.html",
                           subs=subs, payments=payments,
                           nmo=nmo, nan=nan, mrr=mrr, arr=arr)


@admin_bp.route("/abonnements/<int:user_id>/annuler", methods=["POST"])
@admin_required
def cancel_sub(user_id):
    user = User.query.get_or_404(user_id)
    import stripe
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    if user.stripe_subscription_id:
        try:
            stripe.Subscription.cancel(user.stripe_subscription_id)
        except stripe.error.StripeError:
            pass
    user.plan = "free"; user.plan_status = "inactive"
    user.stripe_subscription_id = None
    db.session.commit()
    flash(f"Abonnement de {user.full_name} annulé.", "success")
    return redirect(url_for("admin.subscriptions"))


# ══════════════════════════════════════════════════════════
# PARAMÈTRES PAIEMENT
# ══════════════════════════════════════════════════════════
@admin_bp.route("/paiement", methods=["GET", "POST"])
@admin_required
def payment_settings():
    ps = PaymentSettings.query.first() or PaymentSettings()
    if request.method == "POST":
        ps.company_name  = request.form.get("company_name", "").strip()
        ps.siret         = request.form.get("siret", "").strip()
        ps.vat_number    = request.form.get("vat_number", "").strip()
        ps.iban          = request.form.get("iban", "").strip()
        ps.bic           = request.form.get("bic", "").strip()
        ps.bank_owner    = request.form.get("bank_owner", "").strip()
        ps.bank_name     = request.form.get("bank_name", "").strip()
        ps.paypal_email  = request.form.get("paypal_email", "").strip()
        try:
            ps.monthly_price = int(float(request.form.get("monthly_price", 29)) * 100)
            ps.annual_price  = int(float(request.form.get("annual_price", 279)) * 100)
        except ValueError:
            pass
        if not ps.id:
            db.session.add(ps)
        db.session.commit()
        flash("Paramètres de paiement enregistrés.", "success")
        return redirect(url_for("admin.payment_settings"))
    return render_template("admin/payment_settings.html", ps=ps)
