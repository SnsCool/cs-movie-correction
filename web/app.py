"""
講師入力Webフォーム — Flask アプリケーション
テンプレート画像・講師画像をビジュアルで選択し、Notionマスターテーブルに書き込む。
Zoom録画完了後、既存パイプラインが自動処理を実行する。
"""

import json
import logging
import os
import re
import secrets
import sys
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    session,
)
from dotenv import load_dotenv

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

load_dotenv(PROJECT_ROOT / ".env")

import notion  # noqa: E402

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

LECTURER_IMAGES_DIR = PROJECT_ROOT / "assets" / "lecturer-images"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

VALID_CATEGORIES = {"1on1", "グルコン", "講座"}
MAX_TEXT_LENGTH = 500


# ---------------------------------------------------------------------------
# Image / Template scanning (cached at startup)
# ---------------------------------------------------------------------------

_cached_lecturers: list[dict] | None = None
_cached_templates: list[dict] | None = None


def _scan_lecturer_images() -> list[dict]:
    """Scan assets/lecturer-images/ and build a structured registry."""
    images = []
    for f in sorted(LECTURER_IMAGES_DIR.glob("*.png")):
        stem = f.stem
        parts = stem.split("_")
        if len(parts) < 3:
            continue
        img_id = parts[0]
        img_type = parts[-1]
        names = parts[1:-1]
        images.append({
            "id": img_id,
            "filename": f.name,
            "names": names,
            "label": " x ".join(names),
            "type": img_type,
            "url": f"/images/lecturers/{f.name}",
        })
    return images


def _scan_templates() -> list[dict]:
    """Scan templates/pattern{1,2,3}/ and build a preview registry."""
    templates = []
    for pattern_dir in sorted(TEMPLATES_DIR.glob("pattern*")):
        config_path = pattern_dir / "config.json"
        if not config_path.exists():
            continue
        with open(config_path, encoding="utf-8") as fh:
            config = json.load(fh)
        templates.append({
            "dir": pattern_dir.name,
            "name": config.get("name", pattern_dir.name),
            "description": config.get("description", ""),
            "preview_url": f"/images/templates/{pattern_dir.name}/base.png",
        })
    return templates


def get_lecturers() -> list[dict]:
    global _cached_lecturers
    if _cached_lecturers is None:
        _cached_lecturers = _scan_lecturer_images()
    return _cached_lecturers


def get_templates() -> list[dict]:
    global _cached_templates
    if _cached_templates is None:
        _cached_templates = _scan_templates()
    return _cached_templates


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------

def _generate_csrf_token() -> str:
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def _validate_csrf_token() -> bool:
    token = session.get("_csrf_token", "")
    submitted = request.form.get("_csrf_token", "")
    return token and submitted and secrets.compare_digest(token, submitted)


app.jinja_env.globals["csrf_token"] = _generate_csrf_token


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def _get_valid_pattern_names() -> set[str]:
    return {t["name"] for t in get_templates()}


def _get_valid_lecturer_filenames() -> set[str]:
    return {img["filename"] for img in get_lecturers()}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def form():
    lecturers = get_lecturers()
    templates = get_templates()
    return render_template("form.html", lecturers=lecturers, templates=templates)


@app.route("/submit", methods=["POST"])
def submit():
    try:
        # CSRF check
        if not _validate_csrf_token():
            return render_template("success.html", error="不正なリクエストです。フォームを再読み込みしてください。"), 403

        title = request.form.get("title", "").strip()[:MAX_TEXT_LENGTH]
        thumbnail_text = request.form.get("thumbnail_text", "").strip()[:MAX_TEXT_LENGTH]
        category = request.form.get("category", "").strip()
        start_time = request.form.get("start_time", "").strip()
        pattern = request.form.get("pattern", "").strip()

        # パターンごとのフィールドを取得
        lecturer_name = ""
        lecturer_image1 = ""
        lecturer_image2 = ""
        student_name = ""

        if pattern == "パターン1":
            lecturer_name = request.form.get("lecturer_name", "").strip()[:MAX_TEXT_LENGTH]
            lecturer_image1 = request.form.get("lecturer_image1", "").strip()
            lecturer_image2 = request.form.get("lecturer_image2", "").strip()
        elif pattern == "パターン2":
            lecturer_name = request.form.get("lecturer_name_p2", "").strip()[:MAX_TEXT_LENGTH]
            lecturer_image1 = request.form.get("lecturer_image_single", "").strip()
        elif pattern == "パターン3":
            lecturer_name = request.form.get("lecturer_name_p3", "").strip()[:MAX_TEXT_LENGTH]
            student_name = request.form.get("student_name", "").strip()[:MAX_TEXT_LENGTH]

        # Validate required fields
        errors = []
        if not title:
            errors.append("タイトルは必須です")
        if not thumbnail_text:
            errors.append("サムネ文言は必須です")
        if not category:
            errors.append("種別は必須です")
        elif category not in VALID_CATEGORIES:
            errors.append("無効な種別です")
        if not start_time:
            errors.append("開始時間は必須です")
        else:
            try:
                datetime.strptime(start_time, "%Y-%m-%dT%H:%M")
            except ValueError:
                errors.append("開始時間の形式が不正です")
        if not pattern:
            errors.append("パターンは必須です")
        elif pattern not in _get_valid_pattern_names():
            errors.append("無効なパターンです")

        # Validate lecturer images against known filenames
        valid_filenames = _get_valid_lecturer_filenames()
        if lecturer_image1 and lecturer_image1 not in valid_filenames:
            errors.append("無効な講師画像が選択されました")
        if lecturer_image2 and lecturer_image2 not in valid_filenames:
            errors.append("無効な講師画像が選択されました")

        if errors:
            lecturers = get_lecturers()
            templates = get_templates()
            return render_template(
                "form.html",
                lecturers=lecturers,
                templates=templates,
                errors=errors,
                form_data=request.form,
            ), 400

        # Convert datetime-local to ISO 8601
        if start_time and "T" in start_time:
            start_time = start_time + ":00"

        page_id = notion.create_master_record(
            title=title,
            thumbnail_text=thumbnail_text,
            category=category,
            start_time=start_time,
            lecturer_name=lecturer_name,
            lecturer_image1=lecturer_image1,
            lecturer_image2=lecturer_image2,
            pattern=pattern,
            student_name=student_name,
        )

        # Validate page_id is a valid UUID before building URL
        clean_id = page_id.replace("-", "")
        if not re.fullmatch(r"[0-9a-f]{32}", clean_id):
            raise ValueError(f"Invalid page_id returned: {page_id}")
        notion_url = f"https://notion.so/{clean_id}"
        return render_template(
            "success.html",
            title=title,
            category=category,
            pattern=pattern,
            notion_url=notion_url,
        )

    except Exception:
        logger.exception("Submit error")
        return render_template(
            "success.html",
            error="送信中にエラーが発生しました。しばらくしてから再度お試しください。",
        ), 500


# ---------------------------------------------------------------------------
# Image serving
# ---------------------------------------------------------------------------

@app.route("/images/lecturers/<path:filename>")
def lecturer_image(filename):
    if filename not in _get_valid_lecturer_filenames():
        return "Not Found", 404
    return send_from_directory(str(LECTURER_IMAGES_DIR), filename)


@app.route("/images/templates/<pattern>/base.png")
def template_image(pattern):
    valid_dirs = {t["dir"] for t in get_templates()}
    if pattern not in valid_dirs:
        return "Not Found", 404
    return send_from_directory(str(TEMPLATES_DIR / pattern), "base.png")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    is_debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=8080, debug=is_debug)
