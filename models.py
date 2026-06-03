"""
Modèles SQLAlchemy — ConstructLearn Pro
"""
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager


# ══════════════════════════════════════════════════════════
# USER
# ══════════════════════════════════════════════════════════
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name    = db.Column(db.String(100), nullable=False)
    last_name     = db.Column(db.String(100), nullable=False)
    role          = db.Column(db.String(20), default="member")   # member | admin
    avatar_url    = db.Column(db.String(500))
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login    = db.Column(db.DateTime)

    # Stripe
    stripe_customer_id     = db.Column(db.String(100), unique=True)
    stripe_subscription_id = db.Column(db.String(100), unique=True)
    plan                   = db.Column(db.String(20), default="free")  # free | monthly | annual
    plan_status            = db.Column(db.String(20), default="inactive")  # active | cancelled | past_due
    plan_expires_at        = db.Column(db.DateTime)

    # Relations
    enrollments = db.relationship("Enrollment", back_populates="user", lazy="dynamic")
    payments    = db.relationship("Payment",    back_populates="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def initials(self):
        return (self.first_name[0] + self.last_name[0]).upper()

    @property
    def is_pro(self):
        return self.plan in ("monthly", "annual") and self.plan_status == "active"

    @property
    def is_admin(self):
        return self.role == "admin"

    def can_access(self, course):
        if self.is_admin:
            return True
        if course.plan_required == "free":
            return True
        return self.is_pro

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ══════════════════════════════════════════════════════════
# COURSE
# ══════════════════════════════════════════════════════════
class Course(db.Model):
    __tablename__ = "courses"

    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(255), nullable=False)
    slug          = db.Column(db.String(255), unique=True, nullable=False, index=True)
    description   = db.Column(db.Text)
    category      = db.Column(db.String(20), nullable=False)   # geo | bim | tp
    emoji         = db.Column(db.String(10), default="🎓")
    duration      = db.Column(db.String(50))
    thumbnail_url = db.Column(db.String(500))
    plan_required = db.Column(db.String(20), default="monthly")  # free | monthly
    published     = db.Column(db.Boolean, default=False)
    order_num     = db.Column(db.Integer, default=0)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Stats (dénormalisées pour performances)
    students_count = db.Column(db.Integer, default=0)
    rating_avg     = db.Column(db.Float,   default=0.0)
    rating_count   = db.Column(db.Integer, default=0)

    # Relations
    videos      = db.relationship("Video",      back_populates="course", order_by="Video.order_num", lazy="dynamic", cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", back_populates="course", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def video_count(self):
        return self.videos.count()

    @property
    def category_label(self):
        return {"geo": "Géotechnique", "bim": "BIM & Revit", "tp": "Travaux Publics"}.get(self.category, self.category)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "slug": self.slug,
            "description": self.description, "category": self.category,
            "emoji": self.emoji, "duration": self.duration,
            "thumbnail_url": self.thumbnail_url,
            "plan_required": self.plan_required, "published": self.published,
            "students": self.students_count, "rating": self.rating_avg,
            "video_count": self.video_count,
        }

    def __repr__(self):
        return f"<Course {self.title}>"


# ══════════════════════════════════════════════════════════
# VIDEO
# ══════════════════════════════════════════════════════════
class Video(db.Model):
    __tablename__ = "videos"

    id          = db.Column(db.Integer, primary_key=True)
    course_id   = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    duration    = db.Column(db.String(20))
    order_num   = db.Column(db.Integer, default=0)
    is_preview  = db.Column(db.Boolean, default=False)

    # Source vidéo
    video_url    = db.Column(db.String(1000))   # Vimeo / YouTube unlisted
    video_file   = db.Column(db.String(500))    # Fichier uploadé (path relatif)
    video_type   = db.Column(db.String(20), default="url")  # url | upload

    # Documents joints
    documents    = db.relationship("VideoDocument", back_populates="video", cascade="all, delete-orphan")

    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relation
    course = db.relationship("Course", back_populates="videos")

    def to_dict(self):
        return {
            "id": self.id, "course_id": self.course_id,
            "title": self.title, "description": self.description,
            "duration": self.duration, "order_num": self.order_num,
            "is_preview": self.is_preview,
            "video_url": self.video_url, "video_type": self.video_type,
            "docs": [d.to_dict() for d in self.documents],
        }

    def __repr__(self):
        return f"<Video {self.title}>"


class VideoDocument(db.Model):
    __tablename__ = "video_documents"

    id         = db.Column(db.Integer, primary_key=True)
    video_id   = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False)
    filename   = db.Column(db.String(255), nullable=False)
    file_path  = db.Column(db.String(500), nullable=False)
    file_size  = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    video = db.relationship("Video", back_populates="documents")

    def to_dict(self):
        return {"id": self.id, "filename": self.filename, "file_size": self.file_size}


# ══════════════════════════════════════════════════════════
# ENROLLMENT
# ══════════════════════════════════════════════════════════
class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (db.UniqueConstraint("user_id", "course_id"),)

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"),   nullable=False)
    course_id   = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    progress    = db.Column(db.Integer, default=0)   # 0-100 %
    completed   = db.Column(db.Boolean, default=False)
    enrolled_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at= db.Column(db.DateTime)

    user   = db.relationship("User",   back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")

    def __repr__(self):
        return f"<Enrollment user={self.user_id} course={self.course_id}>"


# ══════════════════════════════════════════════════════════
# PAYMENT
# ══════════════════════════════════════════════════════════
class Payment(db.Model):
    __tablename__ = "payments"

    id                    = db.Column(db.Integer, primary_key=True)
    user_id               = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    stripe_payment_intent = db.Column(db.String(100), unique=True)
    stripe_invoice_id     = db.Column(db.String(100))
    amount_cents          = db.Column(db.Integer, nullable=False)
    currency              = db.Column(db.String(3), default="eur")
    plan                  = db.Column(db.String(20))   # monthly | annual
    status                = db.Column(db.String(20), default="pending")  # pending | paid | failed | refunded
    created_at            = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="payments")

    @property
    def amount_euros(self):
        return self.amount_cents / 100

    def __repr__(self):
        return f"<Payment {self.amount_euros}€ {self.status}>"


# ══════════════════════════════════════════════════════════
# PAYMENT SETTINGS (stocké en base, 1 seule ligne)
# ══════════════════════════════════════════════════════════
class PaymentSettings(db.Model):
    __tablename__ = "payment_settings"

    id           = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255))
    siret        = db.Column(db.String(50))
    vat_number   = db.Column(db.String(50))
    iban         = db.Column(db.String(50))
    bic          = db.Column(db.String(20))
    bank_owner   = db.Column(db.String(255))
    bank_name    = db.Column(db.String(255))
    paypal_email = db.Column(db.String(255))
    monthly_price= db.Column(db.Integer, default=2900)   # centimes
    annual_price = db.Column(db.Integer, default=27900)  # centimes
    updated_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
