"""Authentication routes and helpers."""

from functools import wraps
from typing import Any, Dict

from flask import (
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .storage import save_users


def login_required(f):
    """Ensure a user is logged in before accessing a route."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def register_auth_routes(app, users: Dict[str, Any]) -> None:
    """Register login/logout/register routes on the app."""

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            if username in users and users[username] == password:
                session["user"] = username
                flash("Logged in successfully!", "success")
                return redirect(url_for("index"))
            flash("Invalid username or password", "error")
            return redirect(url_for("login"))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.pop("user", None)
        flash("Logged out", "success")
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            confirm_password = request.form.get("confirm_password")
            if username in users:
                flash("Username already exists", "error")
                return redirect(url_for("register"))
            if password != confirm_password:
                flash("Passwords do not match", "error")
                return redirect(url_for("register"))
            users[username] = password
            save_users(users)
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        return render_template("register.html")
