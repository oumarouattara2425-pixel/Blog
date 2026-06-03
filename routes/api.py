"""
Routes API JSON — ConstructLearn Pro
"""
from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import Course, Video, Enrollment

api_bp = Blueprint("api", __name__)


@api_bp.route("/progression/<int:course_id>", methods=["POST"])
@login_required
def update_progress(course_id):
    data = request.get_json(silent=True) or {}
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id
    ).first()
    if not enrollment:
        return jsonify({"error": "Non inscrit"}), 404
    progress = int(data.get("progress", 0))
    enrollment.progress = max(enrollment.progress, min(progress, 100))
    if enrollment.progress == 100 and not enrollment.completed:
        from datetime import datetime, timezone
        enrollment.completed    = True
        enrollment.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"ok": True, "progress": enrollment.progress, "completed": enrollment.completed})


@api_bp.route("/cours/<int:course_id>/videos")
@login_required
def course_videos(course_id):
    course = Course.query.get_or_404(course_id)
    if not current_user.can_access(course):
        abort(403)
    videos = [v.to_dict() for v in course.videos.order_by(Video.order_num).all()]
    return jsonify(videos)


@api_bp.route("/stats")
@login_required
def user_stats():
    if not current_user.is_admin:
        abort(403)
    from models import User, Payment
    return jsonify({
        "users":    User.query.count(),
        "pro":      User.query.filter(User.plan != "free").count(),
        "revenue":  (db.session.query(db.func.sum(Payment.amount_cents))
                     .filter_by(status="paid").scalar() or 0) / 100,
    })
