"""Admin dashboard and management routes."""

from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from deps import render
from models import User, Challenge, Flag, Score, Submission, SiteConfig, get_site_config

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request):
    user = request.state.user
    if not user.is_authenticated or not user.is_admin:
        return RedirectResponse(url="/", status_code=303)
    return None


def _latest_correct_submission(db, score):
    return (
        db.query(Submission)
        .filter_by(user_id=score.user_id, challenge_id=score.challenge_id, flag_id=score.flag_id, is_correct=True)
        .order_by(Submission.submitted_at.desc())
        .first()
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", name="admin.dashboard")
def dashboard(request: Request):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    user = request.state.user

    from challenge_catalog import get_catalog_by_order
    catalog = get_catalog_by_order()

    pending_scores = db.query(Score).filter_by(is_approved=False).order_by(Score.awarded_at.desc()).all()
    pending_rows = []
    for score in pending_scores:
        latest = _latest_correct_submission(db, score)
        challenge = db.query(Challenge).get(score.challenge_id)
        cfg = catalog.get(challenge.order_position, {}) if challenge else {}
        pending_rows.append({
            "score": score,
            "latest_flag_value": latest.submitted_flag if latest else "",
            "submitted_at": latest.submitted_at if latest else score.awarded_at,
            "flag_points_max": cfg.get("flag_points_max", 0),
            "explanation_points_max": cfg.get("explanation_points_max", 0),
        })

    users = db.query(User).order_by(User.created_at.desc()).all()
    evaluators = db.query(User).filter((User.is_evaluator == True) | (User.is_admin == True)).order_by(User.username).all()
    participants = db.query(User).filter(User.is_admin == False, User.is_evaluator == False).order_by(User.username).all()
    challenges = db.query(Challenge).order_by(Challenge.order_position).all()
    total_approved = db.query(Score).filter_by(is_approved=True).count()
    site_config = get_site_config(db)

    return render(
        "admin_dashboard.html",
        request,
        pending_rows=pending_rows,
        users=users,
        evaluators=evaluators,
        participants=participants,
        challenges=challenges,
        total_approved_scores=total_approved,
        is_leaderboard_public=site_config.leaderboard_public,
        event_active=site_config.event_active,
        active_round=site_config.active_round,
    )


# ── Score approval / rejection ───────────────────────────────────────────────

@router.post("/approve-score/{score_id}", name="admin.approve_score")
def approve_score(request: Request, score_id: int, flag_points: int = Form(0), explanation_points: int = Form(0)):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    user = request.state.user

    from challenge_catalog import get_catalog_by_order
    score = db.query(Score).get(score_id)
    if score:
        challenge = db.query(Challenge).get(score.challenge_id)
        catalog = get_catalog_by_order()
        cfg = catalog.get(challenge.order_position, {}) if challenge else {}
        flag_max = cfg.get("flag_points_max", 0)
        expl_max = cfg.get("explanation_points_max", 0)

        flag_pts = max(0, min(flag_points, flag_max))
        expl_pts = max(0, min(explanation_points, expl_max))

        score.flag_points = flag_pts
        score.explanation_points = expl_pts
        score.points = flag_pts + expl_pts
        score.is_approved = True
        score.approved_by = user.id
        score.approved_at = datetime.utcnow()
        score.leaderboard_visible = True

        target_user = db.query(User).get(score.user_id)
        target_user.total_points = target_user.get_total_points(db)
        db.commit()

    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


@router.post("/reject-score/{score_id}", name="admin.reject_score")
def reject_score(request: Request, score_id: int):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    score = db.query(Score).get(score_id)
    if score:
        db.delete(score)
        db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


# ── Leaderboard visibility ──────────────────────────────────────────────────

@router.post("/toggle-leaderboard", name="admin.toggle_leaderboard")
def toggle_leaderboard(request: Request):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    config = get_site_config(db)
    config.leaderboard_public = not config.leaderboard_public
    db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


# ── User management ─────────────────────────────────────────────────────────

@router.post("/users/{user_id}/toggle-evaluator", name="admin.toggle_evaluator")
def toggle_evaluator(request: Request, user_id: int):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    target = db.query(User).get(user_id)
    if target and target.id != request.state.user.id and not target.is_admin:
        target.is_evaluator = not target.is_evaluator
        db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


@router.post("/users/{user_id}/approve", name="admin.approve_user")
def approve_user(request: Request, user_id: int):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    target = db.query(User).get(user_id)
    if target and target.id != request.state.user.id:
        target.is_approved = True
        db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


@router.post("/users/{user_id}/reject-user", name="admin.reject_user")
def reject_user(request: Request, user_id: int):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    target = db.query(User).get(user_id)
    if target and target.id != request.state.user.id and not target.is_admin:
        db.delete(target)
        db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


@router.post("/users/{user_id}/delete", name="admin.delete_user")
def delete_user(request: Request, user_id: int):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    target = db.query(User).get(user_id)
    if target and target.id != request.state.user.id:
        db.delete(target)
        db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


# ── Event controls ───────────────────────────────────────────────────────────

@router.post("/toggle-event", name="admin.toggle_event")
def toggle_event(request: Request):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    config = get_site_config(db)
    config.event_active = not config.event_active
    db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


# ── Round management ─────────────────────────────────────────────────────────

@router.post("/set-active-round", name="admin.set_active_round")
def set_active_round(request: Request, round_number: int = Form(...)):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    config = get_site_config(db)
    if round_number in (0, 1, 2, 3):
        config.active_round = round_number
        db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


# ── Challenge reveal / hide ──────────────────────────────────────────────────

@router.post("/challenges/{challenge_id}/toggle-reveal", name="admin.toggle_challenge_reveal")
def toggle_challenge_reveal(request: Request, challenge_id: int):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    ch = db.query(Challenge).get(challenge_id)
    if ch:
        ch.is_revealed = not ch.is_revealed
        db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


@router.post("/reveal-all", name="admin.reveal_all_challenges")
def reveal_all_challenges(request: Request):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    db.query(Challenge).update({Challenge.is_revealed: True}, synchronize_session=False)
    db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


@router.post("/hide-all", name="admin.hide_all_challenges")
def hide_all_challenges(request: Request):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    db.query(Challenge).update({Challenge.is_revealed: False}, synchronize_session=False)
    db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


# ── Challenge content update ─────────────────────────────────────────────────

@router.post("/challenges/{challenge_id}/update", name="admin.update_challenge")
def update_challenge(
    request: Request,
    challenge_id: int,
    title: str = Form(""),
    category: str = Form(""),
    difficulty: str = Form(""),
    description: str = Form(""),
    total_points: str = Form(""),
    flag_content: str = Form(""),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    ch = db.query(Challenge).get(challenge_id)
    if not ch:
        return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)

    try:
        tp = max(1, int(total_points))
    except (TypeError, ValueError):
        tp = ch.total_points

    if title.strip():
        ch.title = title.strip()
    if category.strip():
        ch.category = category.strip()
    if difficulty.strip():
        ch.difficulty = difficulty.strip()
    if description.strip():
        ch.description = description.strip()
    ch.total_points = tp

    final_flag = db.query(Flag).filter_by(challenge_id=ch.id, flag_order=1).first()
    if final_flag is None:
        final_flag = Flag(
            challenge_id=ch.id,
            flag_order=1,
            flag_content=flag_content.strip() or f"flag{{challenge_{ch.id}_final}}",
            points_value=tp,
            description="Final verification flag",
        )
        db.add(final_flag)
    else:
        if flag_content.strip():
            final_flag.flag_content = flag_content.strip()
        final_flag.points_value = tp
        final_flag.description = "Final verification flag"

    # Remove extra flags
    extras = db.query(Flag).filter(Flag.challenge_id == ch.id, Flag.flag_order != 1).all()
    for f in extras:
        db.delete(f)

    db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


# ── Evaluator assignment ──────────────────────────────────────────────────────

@router.post("/assign-evaluator", name="admin.assign_evaluator")
def assign_evaluator(
    request: Request,
    participant_id: int = Form(...),
    evaluator_id: int = Form(...),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    participant = db.query(User).get(participant_id)
    evaluator = db.query(User).get(evaluator_id)

    if not participant or not evaluator:
        return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)
    if not (evaluator.is_evaluator or evaluator.is_admin):
        return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)

    participant.assigned_evaluator_id = evaluator.id
    db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


@router.post("/unassign-evaluator/{user_id}", name="admin.unassign_evaluator")
def unassign_evaluator(request: Request, user_id: int):
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    participant = db.query(User).get(user_id)
    if participant:
        participant.assigned_evaluator_id = None
        db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)


@router.post("/bulk-assign-evaluator", name="admin.bulk_assign_evaluator")
def bulk_assign_evaluator(
    request: Request,
    evaluator_id: int = Form(...),
):
    """Auto-assign all unassigned participants to one specific evaluator."""
    redirect = _require_admin(request)
    if redirect:
        return redirect

    db = request.state.db
    unassigned = db.query(User).filter(
        User.is_admin == False,
        User.is_evaluator == False,
        User.assigned_evaluator_id == None,
    ).all()

    for participant in unassigned:
        participant.assigned_evaluator_id = evaluator_id

    db.commit()
    return RedirectResponse(url=request.url_for("admin.dashboard"), status_code=303)
