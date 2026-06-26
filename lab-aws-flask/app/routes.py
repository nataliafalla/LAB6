from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required

from . import db
from .models import User
from .s3_utils import upload_profile_image, delete_profile_image

users_bp = Blueprint("users", __name__)


@users_bp.route("/")
@login_required
def index():
    return redirect(url_for("users.list_users"))


@users_bp.route("/users")
@login_required
def list_users():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter((User.full_name.ilike(like)) | (User.email.ilike(like)))
    users = query.order_by(User.created_at.desc()).all()
    return render_template("users_list.html", users=users, q=q)


@users_bp.route("/users/new", methods=["GET", "POST"])
@login_required
def create_user():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "user").strip()

        if not full_name or not email:
            flash("Nombre y email son obligatorios", "error")
            return render_template("user_form.html", user=None)

        if User.query.filter_by(email=email).first():
            flash("Ese email ya existe", "error")
            return render_template("user_form.html", user=None)

        image = request.files.get("image")
        key, url = upload_profile_image(image) if image else (None, None)

        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            role=role,
            image_key=key,
            image_url=url,
        )
        db.session.add(user)
        db.session.commit()
        flash("Usuario creado correctamente", "success")
        return redirect(url_for("users.list_users"))
    return render_template("user_form.html", user=None)


@users_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        user.full_name = request.form.get("full_name", user.full_name).strip()
        user.email = request.form.get("email", user.email).strip().lower()
        user.phone = request.form.get("phone", user.phone or "").strip()
        user.role = request.form.get("role", user.role).strip()

        image = request.files.get("image")
        if image and image.filename:
            new_key, new_url = upload_profile_image(image)
            if new_key:
                if user.image_key:
                    delete_profile_image(user.image_key)
                user.image_key = new_key
                user.image_url = new_url

        db.session.commit()
        flash("Usuario actualizado", "success")
        return redirect(url_for("users.list_users"))
    return render_template("user_form.html", user=user)


@users_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.image_key:
        delete_profile_image(user.image_key)
    db.session.delete(user)
    db.session.commit()
    flash("Usuario eliminado", "success")
    return redirect(url_for("users.list_users"))


@users_bp.route("/health")
def health():
    return {"status": "ok"}, 200
