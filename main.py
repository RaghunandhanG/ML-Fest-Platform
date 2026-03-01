"""
Combined CTF Platform + Evaluation API — FastAPI
=================================================
Single-process app that serves:
  - The web UI (templates)
  - JSON API for flag submission, leaderboard, downloads
  - Evaluation endpoints at /evaluate/challenge-{1..5}
"""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from config import SECRET_KEY, UPLOAD_FOLDER
from database import Base, engine, SessionLocal
from deps import render, ANONYMOUS
from models import User, Challenge, Flag, SiteConfig, UserFlag, get_site_config
from challenge_catalog import CATALOG, get_catalog_by_order

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Startup helpers ──────────────────────────────────────────────────────────

def sync_challenge_catalog(db):
    """Seed challenges / flags from catalog without overwriting admin edits."""
    by_order = get_catalog_by_order()
    existing = {c.order_position: c for c in db.query(Challenge).all()}

    for order, cfg in by_order.items():
        challenge = existing.get(order)
        primary_file = cfg["resources"][0]["local_name"] if cfg["resources"] else None
        if challenge is None:
            challenge = Challenge(order_position=order)
            db.add(challenge)
        challenge.title = cfg["title"]
        challenge.description = cfg["description"]
        challenge.category = cfg["category"]
        challenge.difficulty = cfg["difficulty"]
        challenge.total_points = cfg["total_points"]
        challenge.source_file_path = primary_file

        db.flush()
        existing_flags = {f.flag_order: f for f in challenge.flags}
        for flag_cfg in cfg["flags"]:
            flag = existing_flags.get(flag_cfg["flag_order"])
            if flag is None:
                flag = Flag(challenge_id=challenge.id, flag_order=flag_cfg["flag_order"])
                db.add(flag)
                flag.flag_content = flag_cfg["flag_content"]
                flag.points_value = flag_cfg["points_value"]
                flag.description = flag_cfg["description"]

        for forder, flag in list(existing_flags.items()):
            if forder not in {f["flag_order"] for f in cfg["flags"]}:
                db.delete(flag)

        main_flag = db.query(Flag).filter_by(challenge_id=challenge.id, flag_order=1).first()
        if main_flag:
            main_flag.points_value = challenge.total_points
            if not main_flag.description:
                main_flag.description = "Final verification flag"

    db.commit()


def ensure_default_admin(db):
    from config import ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD

    if db.query(User).filter_by(is_admin=True).first():
        return

    existing = db.query(User).filter(
        (User.username == ADMIN_USERNAME) | (User.email == ADMIN_EMAIL)
    ).first()
    if existing:
        existing.is_admin = True
        existing.is_approved = True
        if not existing.password_hash:
            existing.set_password(ADMIN_PASSWORD)
        db.commit()
        return

    admin = User(username=ADMIN_USERNAME, email=ADMIN_EMAIL, is_admin=True, is_approved=True)
    admin.set_password(ADMIN_PASSWORD)
    db.add(admin)
    db.commit()


def ensure_challenge_files():
    """Download challenge assets into static/challenge_files if missing."""
    import requests as req_lib

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    for cfg in CATALOG:
        for item in cfg["resources"]:
            fpath = os.path.join(UPLOAD_FOLDER, item["local_name"])
            if os.path.exists(fpath):
                continue
            try:
                r = req_lib.get(item["url"], timeout=20)
                r.raise_for_status()
                with open(fpath, "wb") as f:
                    f.write(r.content)
            except Exception:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("Challenge asset could not be downloaded automatically.\n")
                    f.write(f"Source: {item['url']}\n")


def ensure_site_config(db):
    """Ensure a SiteConfig singleton row exists."""
    get_site_config(db)


def init_data():
    db = SessionLocal()
    try:
        sync_challenge_catalog(db)
        ensure_default_admin(db)
        ensure_site_config(db)
    finally:
        db.close()
    ensure_challenge_files()


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    init_data()
    yield


app = FastAPI(title="Team Qernels CTF", version="1.0.0", lifespan=lifespan)


# ── Middleware ────────────────────────────────────────────────────────────────
# Order matters: the @app.middleware decorator adds an inner middleware,
# then add_middleware(SessionMiddleware) wraps as outer.
# Execution: SessionMiddleware -> db_session_middleware -> route handler.

@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    """Open a DB session for every request; load user from session cookie."""
    session = SessionLocal()
    request.state.db = session
    try:
        user_id = request.session.get("user_id")
        if user_id:
            user = session.query(User).get(user_id)
            request.state.user = user if user else ANONYMOUS
        else:
            request.state.user = ANONYMOUS
        request.state.site_config = get_site_config(session)
        response = await call_next(request)
        # Prevent browsers/proxies from caching user-specific pages
        response.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        response.headers.setdefault("Pragma", "no-cache")
        return response
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="ctf_session",
    max_age=14 * 24 * 60 * 60,
    same_site="lax",
    https_only=False,
    path="/",
)


# ── Static files ─────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


# ── Include routers ──────────────────────────────────────────────────────────

from routes import auth, api, challenges, admin, evaluator, evaluation, round1, round2  # noqa: E402

app.include_router(auth.router)
app.include_router(api.router)
app.include_router(challenges.router)
app.include_router(admin.router)
app.include_router(evaluator.router)
app.include_router(evaluation.router)
app.include_router(round1.router)
app.include_router(round2.router)


# ── Root routes ──────────────────────────────────────────────────────────────

@app.get("/", name="index")
def index(request: Request):
    return render("index.html", request)


@app.get("/health")
def health():
    return {"status": "healthy"}


# ── Error handlers ───────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse({"success": False, "message": "Not found"}, 404)


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    if hasattr(request.state, "db"):
        request.state.db.rollback()
    return JSONResponse({"success": False, "message": "Internal server error"}, 500)


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("APP_PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
