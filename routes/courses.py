"""
Routes formations & vidéos — ConstructLearn Pro
"""
import os
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, send_from_directory, current_app)
from flask_login import login_required, current_user
from extensions import db
from models import Course, Video, Enrollment, VideoDocument
from utils import save_uploaded_file, allowed_video, allowed_doc

courses_bp = Blueprint("courses", __name__)


# ── Liste des formations ────────────────────────────────────
@courses_bp.route("/")
@login_required
def index():
    cat = request.args.get("cat", "all")
    q   = request.args.get("q",   "").strip()
    query = Course.query.filter_by(published=True)
    if cat != "all":
        query = query.filter_by(category=cat)
    if q:
        query = query.filter(Course.title.ilike(f"%{q}%"))
    courses = query.order_by(Course.order_num).all()
    enrolled_ids = {
        e.course_id for e in
        Enrollment.query.filter_by(user_id=current_user.id).all()
    }
    return render_template("courses/index.html",
                           courses=courses, cat=cat, q=q,
                           enrolled_ids=enrolled_ids)


# ── Détail d'une formation ──────────────────────────────────
@courses_bp.route("/<slug>")
@login_required
def detail(slug):
    course = Course.query.filter_by(slug=slug, published=True).first_or_404()
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course.id
    ).first()
    videos = course.videos.all()
    can_access = current_user.can_access(course)
    return render_template("courses/detail.html",
                           course=course, videos=videos,
                           enrollment=enrollment, can_access=can_access)


# ── S'inscrire à une formation ─────────────────────────────
@courses_bp.route("/<slug>/inscrire", methods=["POST"])
@login_required
def enroll(slug):
    course = Course.query.filter_by(slug=slug, published=True).first_or_404()
    if not current_user.can_access(course):
        flash("Abonnement Pro requis pour accéder à cette formation.", "warning")
        return redirect(url_for("billing.plans"))
    existing = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course.id
    ).first()
    if not existing:
        e = Enrollment(user_id=current_user.id, course_id=course.id)
        db.session.add(e)
        course.students_count = (course.students_count or 0) + 1
        db.session.commit()
        flash(f"Vous êtes inscrit à « {course.title} » !", "success")
    return redirect(url_for("courses.player", slug=slug, video_id=course.videos.first().id if course.videos.count() else 0))


# ── Lecteur vidéo ───────────────────────────────────────────
@courses_bp.route("/<slug>/video/<int:video_id>")
@login_required
def player(slug, video_id):
    course = Course.query.filter_by(slug=slug, published=True).first_or_404()
    video  = Video.query.filter_by(id=video_id, course_id=course.id).first_or_404()
    if not current_user.can_access(course) and not video.is_preview:
        flash("Abonnement Pro requis pour voir cette vidéo.", "warning")
        return redirect(url_for("billing.plans"))
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course.id
    ).first()
    videos = course.videos.all()
    # Vidéo précédente / suivante
    idx  = next((i for i, v in enumerate(videos) if v.id == video_id), 0)
    prev_video = videos[idx - 1] if idx > 0 else None
    next_video = videos[idx + 1] if idx < len(videos) - 1 else None
    return render_template("courses/player.html",
                           course=course, video=video, videos=videos,
                           enrollment=enrollment,
                           prev_video=prev_video, next_video=next_video)


# ── Mettre à jour la progression ───────────────────────────
@courses_bp.route("/<slug>/progression", methods=["POST"])
@login_required
def update_progress(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course.id
    ).first_or_404()
    progress = int(request.form.get("progress", 0))
    enrollment.progress = min(max(progress, enrollment.progress), 100)
    if enrollment.progress == 100 and not enrollment.completed:
        from datetime import datetime, timezone
        enrollment.completed    = True
        enrollment.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"ok": True, "progress": enrollment.progress}


# ── Télécharger un document joint ──────────────────────────
@courses_bp.route("/document/<int:doc_id>")
@login_required
def download_doc(doc_id):
    doc = VideoDocument.query.get_or_404(doc_id)
    course = doc.video.course
    if not current_user.can_access(course):
        abort(403)
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(upload_dir, doc.file_path, as_attachment=True, download_name=doc.filename)


# ── Servir les vidéos uploadées (protégé) ──────────────────
@courses_bp.route("/video-stream/<path:filename>")
@login_required
def stream_video(filename):
    """Sert les fichiers vidéo uploadés avec contrôle d'accès."""
    # Retrouver la vidéo par son chemin
    video = Video.query.filter_by(video_file=filename).first_or_404()
    if not current_user.can_access(video.course) and not video.is_preview:
        abort(403)
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(upload_dir, filename)
