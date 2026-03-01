"""Challenge page routes (list, detail, dashboard, leaderboard)."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from deps import render
from models import User, Challenge, Flag, UserFlag, get_site_config
from challenge_catalog import get_resources_by_order

router = APIRouter(tags=["challenges"])


def _is_staff(request: Request) -> bool:
    user = request.state.user
    return user.is_authenticated and (user.is_admin or user.is_evaluator)


def _get_event_active(db) -> bool:
    config = get_site_config(db)
    return config.event_active


@router.get("/challenges", name="challenges.list_challenges")
def list_challenges(request: Request):
    db = request.state.db
    user = request.state.user
    if _is_staff(request):
        challenges = db.query(Challenge).order_by(Challenge.order_position).all()
    else:
        challenges = db.query(Challenge).filter_by(is_revealed=True).order_by(Challenge.order_position).all()

    if user.is_authenticated:
        for ch in challenges:
            ch.user_progress = ch.get_user_progress(db, user.id)

    return render("challenges.html", request, challenges=challenges, event_active=_get_event_active(db))


@router.get("/challenges/{challenge_id}", name="challenges.view_challenge")
@router.get("/challenge/{challenge_id}", name="challenges.view_challenge_alt")
def view_challenge(request: Request, challenge_id: int):
    db = request.state.db
    user = request.state.user

    ch = db.query(Challenge).get(challenge_id)
    if not ch:
        return RedirectResponse(url="/challenges", status_code=303)

    if not ch.is_revealed and not _is_staff(request):
        return RedirectResponse(url="/challenges", status_code=303)

    progress = {}
    user_flags = {}  # flag_id -> flag_value for this user
    if user.is_authenticated:
        progress = ch.get_user_progress(db, user.id)
        ufs = db.query(UserFlag).filter_by(user_id=user.id, challenge_id=ch.id).all()
        user_flags = {uf.flag_id: uf.flag_value for uf in ufs}

    resources = get_resources_by_order().get(ch.order_position, [])
    return render("challenge.html", request, challenge=ch, progress=progress, resources=resources, event_active=_get_event_active(db), user_flags=user_flags)


@router.get("/dashboard", name="challenges.dashboard")
def dashboard(request: Request):
    user = request.state.user
    if not user.is_authenticated:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = request.state.db
    challenges = db.query(Challenge).order_by(Challenge.order_position).all()
    progress_data = {ch.id: ch.get_user_progress(db, user.id) for ch in challenges}
    # Compute actual total points from Score table
    computed_total = user.get_total_points(db)
    # Keep cached column in sync
    if user.total_points != computed_total:
        user.total_points = computed_total
        db.commit()
    max_possible = sum(ch.total_points for ch in challenges)
    completed_count = sum(1 for p in progress_data.values() if p["completed_flags"] > 0)
    overall_pct = round(computed_total / max_possible * 100) if max_possible > 0 else 0
    evaluator = db.query(User).get(user.assigned_evaluator_id) if user.assigned_evaluator_id else None
    evaluator_name = evaluator.username if evaluator else None
    return render("dashboard.html", request, computed_total=computed_total, max_possible=max_possible, completed_count=completed_count, overall_pct=overall_pct, evaluator_name=evaluator_name)


@router.get("/leaderboard", name="challenges.leaderboard")
def leaderboard(request: Request):
    return render("leaderboard.html", request)
