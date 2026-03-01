"""Authentication routes (register, login, logout, profile)."""

import re
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from deps import render
from models import User, generate_user_flags

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


def _validate_email(email: str) -> bool:
    return re.match(EMAIL_REGEX, email) is not None


def _validate_password(password: str):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, "Valid"


# ── Register ──────────────────────────────────────────────────────────────────

@router.get("/register", name="auth.register")
def register_page(request: Request):
    return render("register.html", request)


@router.post("/register", name="auth.register_post")
async def register(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    db = request.state.db
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username or not email or not password:
        return JSONResponse({"success": False, "message": "Username, email, and password are required"}, 400)
    if len(username) < 3:
        return JSONResponse({"success": False, "message": "Username must be at least 3 characters"}, 400)
    if not _validate_email(email):
        return JSONResponse({"success": False, "message": "Invalid email format"}, 400)

    ok, msg = _validate_password(password)
    if not ok:
        return JSONResponse({"success": False, "message": msg}, 400)

    if db.query(User).filter_by(username=username).first():
        return JSONResponse({"success": False, "message": "Username already exists"}, 409)
    if db.query(User).filter_by(email=email).first():
        return JSONResponse({"success": False, "message": "Email already registered"}, 409)

    user = User(username=username, email=email, is_approved=True)
    user.set_password(password)
    db.add(user)
    db.commit()

    # Generate one unique flag per challenge for this user
    generate_user_flags(user, db)

    return JSONResponse(
        {
            "success": True,
            "message": "Registration successful! You can now login.",
            "user": {"id": user.id, "username": user.username, "email": user.email},
        },
        201,
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.get("/login", name="auth.login")
def login_page(request: Request):
    return render("login.html", request)


@router.post("/login", name="auth.login_post")
async def login(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    db = request.state.db
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return JSONResponse({"success": False, "message": "Username and password are required"}, 400)

    user = db.query(User).filter_by(username=username).first()
    if not user or not user.check_password(password):
        return JSONResponse({"success": False, "message": "Invalid username or password"}, 401)

    user.last_login = datetime.utcnow()
    db.commit()

    # Ensure per-user flags exist (handles new challenges or existing users)
    generate_user_flags(user, db)

    # Clear any stale session data before setting the new user
    request.session.clear()
    request.session["user_id"] = user.id

    return JSONResponse(
        {
            "success": True,
            "message": "Login successful!",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "total_points": user.total_points,
            },
        },
        200,
    )


# ── Logout ────────────────────────────────────────────────────────────────────

@router.get("/logout", name="auth.logout")
def logout_get(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
def logout_post(request: Request):
    request.session.clear()
    return JSONResponse({"success": True, "message": "Logout successful!"})


# ── Profile helpers ───────────────────────────────────────────────────────────

@router.get("/me")
def get_current_user_info(request: Request):
    user = request.state.user
    if not user.is_authenticated:
        return JSONResponse({"success": False, "message": "Not logged in"}, 401)
    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "total_points": user.total_points,
            "joined_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
    }


@router.get("/profile")
def get_profile(request: Request):
    user = request.state.user
    if not user.is_authenticated:
        return JSONResponse({"success": False, "message": "Not logged in"}, 401)
    db = request.state.db
    completed = user.get_completed_challenges(db)
    return {
        "success": True,
        "profile": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "total_points": user.total_points,
            "challenges_completed": len(completed),
            "joined_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
    }


@router.post("/change-password")
async def change_password(request: Request):
    user = request.state.user
    if not user.is_authenticated:
        return JSONResponse({"success": False, "message": "Not logged in"}, 401)

    data = await request.json()
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not current_password or not new_password:
        return JSONResponse({"success": False, "message": "Current and new passwords are required"}, 400)
    if new_password != confirm_password:
        return JSONResponse({"success": False, "message": "New passwords do not match"}, 400)
    if not user.check_password(current_password):
        return JSONResponse({"success": False, "message": "Current password is incorrect"}, 401)

    ok, msg = _validate_password(new_password)
    if not ok:
        return JSONResponse({"success": False, "message": msg}, 400)

    db = request.state.db
    user.set_password(new_password)
    db.commit()
    return {"success": True, "message": "Password changed successfully!"}
