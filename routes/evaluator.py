"""Evaluator routes — approve/reject flag submissions and assign points."""

from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from deps import render, flash
from models import User, Challenge, Score, Submission

router = APIRouter(prefix="/evaluator", tags=["evaluator"])


def _require_evaluator(request: Request):
    user = request.state.user
    if not user.is_authenticated:
        return RedirectResponse(url="/auth/login", status_code=303)
    if not (user.is_evaluator or user.is_admin):
        return RedirectResponse(url="/", status_code=303)
    return None


def _latest_correct_submission(db, score):
    return (
        db.query(Submission)
        .filter_by(user_id=score.user_id, challenge_id=score.challenge_id, flag_id=score.flag_id, is_correct=True)
        .order_by(Submission.submitted_at.desc())
        .first()
    )


@router.get("/dashboard", name="evaluator.dashboard")
def dashboard(request: Request):
    redirect = _require_evaluator(request)
    if redirect:
        return redirect

    db = request.state.db
    user = request.state.user

    from challenge_catalog import get_catalog_by_order
    catalog = get_catalog_by_order()

    # Only show submissions from participants assigned to this evaluator
    # (admins see everything)
    all_pending = db.query(Score).filter_by(is_approved=False).order_by(Score.awarded_at.desc()).all()
    pending_rows = []
    for score in all_pending:
        # Filter: evaluator only sees their assigned participants (admin sees all)
        if not user.is_admin:
            participant = db.query(User).get(score.user_id)
            if not participant or participant.assigned_evaluator_id != user.id:
                continue

        latest = _latest_correct_submission(db, score)
        challenge = db.query(Challenge).get(score.challenge_id)
        cfg = catalog.get(challenge.order_position, {}) if challenge else {}
        pending_rows.append({
            "score": score,
            "latest_flag_value": latest.submitted_flag if latest else "",
            "submitted_at": latest.submitted_at if latest else score.awarded_at,
            "max_points": challenge.total_points if challenge else 0,
            "flag_points_max": cfg.get("flag_points_max", 0),
            "explanation_points_max": cfg.get("explanation_points_max", 0),
        })

    recent_approved = (
        db.query(Score).filter_by(is_approved=True, approved_by=user.id)
        .order_by(Score.approved_at.desc()).limit(20).all()
    )

    # Get the list of participants assigned to this evaluator
    if user.is_admin:
        assigned_participants = db.query(User).filter(
            User.is_admin == False, User.is_evaluator == False
        ).order_by(User.username).all()
    else:
        assigned_participants = db.query(User).filter_by(
            assigned_evaluator_id=user.id
        ).order_by(User.username).all()

    return render(
        "evaluator_dashboard.html",
        request,
        pending_rows=pending_rows,
        recent_approved=recent_approved,
        assigned_participants=assigned_participants,
    )


@router.post("/approve/{score_id}", name="evaluator.approve_score")
def approve_score(request: Request, score_id: int, flag_points: int = Form(0), explanation_points: int = Form(0)):
    redirect = _require_evaluator(request)
    if redirect:
        return redirect

    db = request.state.db
    user = request.state.user

    from challenge_catalog import get_catalog_by_order
    score = db.query(Score).get(score_id)
    if not score:
        flash(request, "Score entry not found.", "error")
        return RedirectResponse(url=request.url_for("evaluator.dashboard"), status_code=303)

    challenge = db.query(Challenge).get(score.challenge_id)
    catalog = get_catalog_by_order()
    cfg = catalog.get(challenge.order_position, {}) if challenge else {}
    flag_max = cfg.get("flag_points_max", 0)
    expl_max = cfg.get("explanation_points_max", 0)

    flag_pts = max(0, min(flag_points, flag_max))
    expl_pts = max(0, min(explanation_points, expl_max))
    total = flag_pts + expl_pts

    score.flag_points = flag_pts
    score.explanation_points = expl_pts
    score.points = total
    score.is_approved = True
    score.approved_by = user.id
    score.approved_at = datetime.utcnow()
    score.leaderboard_visible = True

    # Flush so the is_approved=True change is visible to the SUM query
    db.flush()

    target_user = db.query(User).get(score.user_id)
    if target_user:
        target_user.total_points = target_user.get_total_points(db)

    db.commit()
    flash(
        request,
        f"Approved {target_user.username if target_user else 'user'} — Flag: {flag_pts}/{flag_max}, Explanation: {expl_pts}/{expl_max} = {total} pts.",
        "success",
    )
    return RedirectResponse(url=request.url_for("evaluator.dashboard"), status_code=303)


@router.post("/reject/{score_id}", name="evaluator.reject_score")
def reject_score(request: Request, score_id: int):
    redirect = _require_evaluator(request)
    if redirect:
        return redirect

    db = request.state.db
    score = db.query(Score).get(score_id)
    if not score:
        flash(request, "Score entry not found.", "error")
        return RedirectResponse(url=request.url_for("evaluator.dashboard"), status_code=303)

    username = score.user.username if score.user else "unknown"
    db.delete(score)
    db.commit()
    flash(request, f"Rejected submission from {username}.", "info")
    return RedirectResponse(url=request.url_for("evaluator.dashboard"), status_code=303)
