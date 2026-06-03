"""
Utilitaires — ConstructLearn Pro
"""
import os
import re
import uuid
from flask import current_app
from werkzeug.utils import secure_filename

# ── Extensions autorisées ───────────────────────────────────
ALLOWED_IMAGE = {"png", "jpg", "jpeg", "webp", "gif"}
ALLOWED_VIDEO = {"mp4", "mov", "avi", "mkv", "webm"}
ALLOWED_DOC   = {"pdf", "docx", "pptx", "xlsx", "zip", "txt"}


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def allowed_image(filename): return _ext(filename) in ALLOWED_IMAGE
def allowed_video(filename): return _ext(filename) in ALLOWED_VIDEO
def allowed_doc(filename):   return _ext(filename) in ALLOWED_DOC


def save_uploaded_file(file_obj, subfolder="misc", allowed=None):
    """
    Sauvegarde un fichier uploadé dans static/uploads/<subfolder>/.
    Retourne le chemin relatif (à partir de uploads/) ou None en cas d'erreur.
    """
    if allowed is None:
        allowed = allowed_image
    if not file_obj or not file_obj.filename:
        return None
    if not allowed(file_obj.filename):
        return None

    ext      = _ext(file_obj.filename)
    filename = f"{uuid.uuid4().hex}.{ext}"
    subdir   = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(subdir, exist_ok=True)
    dest = os.path.join(subdir, filename)
    file_obj.save(dest)
    return f"{subfolder}/{filename}"


def slugify(text):
    """Convertit un titre en slug URL-safe."""
    text = text.lower().strip()
    # Translittération basique FR → ASCII
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "ù": "u", "û": "u", "ü": "u",
        "ô": "o", "ö": "o",
        "î": "i", "ï": "i",
        "ç": "c", "ñ": "n",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text[:100]


def format_size(size_bytes):
    """Formate une taille en octets en chaîne lisible."""
    if size_bytes < 1024:
        return f"{size_bytes} o"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} Ko"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} Mo"
    return f"{size_bytes / 1024 ** 3:.1f} Go"
