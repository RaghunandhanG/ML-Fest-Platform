"""Shared dependencies: DB helper, auth, template rendering, flash messages."""

from starlette.requests import Request
from starlette.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Jinja2 templates ─────────────────────────────────────────────────────────
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.filters["tojson"] = lambda x: json.dumps(x)


# ── AnonymousUser (mimics Flask-Login when not logged in) ─────────────────────
class AnonymousUser:
    is_authenticated = False
    is_admin = False
    is_evaluator = False
    is_approved = False
    is_leaderboard_public = False
    event_active = False
    username = "Anonymous"
    total_points = 0
    id = None


ANONYMOUS = AnonymousUser()


# ── DB dependency ─────────────────────────────────────────────────────────────
def get_db(request: Request) -> Session:
    """Return the request-scoped SQLAlchemy session (set by middleware)."""
    return request.state.db


# ── Flash messages ────────────────────────────────────────────────────────────
def flash(request: Request, message: str, category: str = "info"):
    """Store a flash message in the session cookie."""
    if "_flashes" not in request.session:
        request.session["_flashes"] = []
    request.session["_flashes"].append([category, message])


# ── Template rendering ───────────────────────────────────────────────────────
def render(template_name: str, request: Request, **context):
    """
    Render a Jinja2 template with Flask-compatible helpers:
      - url_for(endpoint, **path_params)
      - current_user
      - get_flashed_messages(with_categories=False)
    """

    def _url_for(__name: str, **kw):
        if __name == "static":
            return "/static/" + kw.get("filename", "")
        return str(request.url_for(__name, **kw))

    flashes = request.session.pop("_flashes", []) if hasattr(request, "session") else []

    ctx = {
        "request": request,
        "current_user": getattr(request.state, "user", ANONYMOUS),
        "url_for": _url_for,
        "get_flashed_messages": lambda with_categories=False: (
            flashes if with_categories else [m for _, m in flashes]
        ),
        **context,
    }
    return templates.TemplateResponse(template_name, ctx)
