"""JSON API routes (flag submission, challenges list, leaderboard, downloads)."""

import os
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, FileResponse

from config import UPLOAD_FOLDER
from models import User, Challenge, Flag, Submission, Score, get_site_config
from challenge_catalog import get_resources_by_order

router = APIRouter(prefix="/api", tags=["api"])

# ── Rate-limiting (in-memory — use Redis in production) ──────────────────────
_submission_tracker: dict[int, list[datetime]] = {}


def _check_rate_limit(user_id: int, max_attempts: int = 5, window: int = 60) -> bool:
    now = datetime.utcnow()
    _submission_tracker.setdefault(user_id, [])
    _submission_tracker[user_id] = [
        t for t in _submission_tracker[user_id] if (now - t).total_seconds() < window
    ]
    return len(_submission_tracker[user_id]) < max_attempts


def _record_attempt(user_id: int):
    _submission_tracker.setdefault(user_id, [])
    _submission_tracker[user_id].append(datetime.utcnow())


# ── Internal submission logic ────────────────────────────────────────────────
def _submit_flag_internal(request: Request, challenge_id, submitted_flag, flag_order=None):
    db = request.state.db
    user = request.state.user

    # Event active?
    config = get_site_config(db)
    if not config.event_active:
        return JSONResponse(
            {"success": False, "message": "The event has not started yet or has ended. Submissions are currently closed."},
            403,
        )

    if not challenge_id or not submitted_flag:
        return JSONResponse({"success": False, "message": "Challenge ID and flag are required"}, 400)

    if not _check_rate_limit(user.id):
        return JSONResponse({"success": False, "message": "Too many attempts. Please wait before trying again."}, 429)
    _record_attempt(user.id)

    challenge = db.query(Challenge).get(challenge_id)
    if not challenge:
        return JSONResponse({"success": False, "message": "Challenge not found"}, 404)

    # Resolve which flag to check
    if flag_order is not None:
        if flag_order != 1:
            return JSONResponse({"success": False, "message": "Only final flag order 1 is valid for this challenge"}, 400)
        if challenge.get_flags_count() != 1:
            return JSONResponse({"success": False, "message": "This challenge does not have exactly 1 final flag configured"}, 400)
        matching_flag = db.query(Flag).filter_by(challenge_id=challenge.id, flag_order=flag_order).first()
        if not matching_flag:
            return JSONResponse({"success": False, "message": f"Flag {flag_order} not found for this challenge"}, 404)
        is_correct = matching_flag.validate_flag(submitted_flag)
    else:
        matching_flag = None
        is_correct = False
        for flag in challenge.flags:
            if flag.validate_flag(submitted_flag):
                matching_flag = flag
                is_correct = True
                break

    if not is_correct:
        sub = Submission(
            user_id=user.id,
            challenge_id=challenge_id,
            flag_id=matching_flag.id if matching_flag else None,
            submitted_flag=submitted_flag,
            is_correct=False,
        )
        db.add(sub)
        db.commit()
        progress = challenge.get_user_progress(db, user.id)
        return JSONResponse({"success": False, "message": "Flag is incorrect. Try again!", "challenge_progress": progress})

    # Already submitted?
    existing_score = db.query(Score).filter_by(user_id=user.id, flag_id=matching_flag.id).first()
    if existing_score:
        progress = challenge.get_user_progress(db, user.id)
        return JSONResponse({"success": False, "message": "You have already submitted this flag.", "points": 0, "challenge_progress": progress})

    points = matching_flag.points_value
    sub = Submission(
        user_id=user.id,
        challenge_id=challenge_id,
        flag_id=matching_flag.id,
        submitted_flag=submitted_flag,
        is_correct=True,
        points_awarded=0,
    )
    score = Score(
        user_id=user.id,
        challenge_id=challenge_id,
        flag_id=matching_flag.id,
        points=points,
        is_approved=False,
    )
    db.add(sub)
    db.add(score)
    db.commit()

    progress = challenge.get_user_progress(db, user.id)
    return JSONResponse(
        {"success": True, "message": "Final flag submitted and pending admin approval.", "pending_points": points, "challenge_progress": progress}
    )


# ── Submit flag ──────────────────────────────────────────────────────────────

@router.post("/submit-flag")
async def submit_flag(request: Request):
    user = request.state.user
    if not user.is_authenticated:
        return JSONResponse({"success": False, "message": "Login required"}, 401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    challenge_id = data.get("challenge_id")
    submitted_flag = (data.get("flag") or "").strip()
    return _submit_flag_internal(request, challenge_id, submitted_flag)


@router.post("/challenges/{challenge_id}/flags/{flag_order}/submit")
async def submit_flag_by_order(request: Request, challenge_id: int, flag_order: int):
    user = request.state.user
    if not user.is_authenticated:
        return JSONResponse({"success": False, "message": "Login required"}, 401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    submitted_flag = (data.get("flag") or "").strip()
    return _submit_flag_internal(request, challenge_id, submitted_flag, flag_order=flag_order)


# ── Challenges (JSON) ────────────────────────────────────────────────────────

@router.get("/challenges")
def get_challenges(request: Request):
    db = request.state.db
    user = request.state.user
    challenges = db.query(Challenge).order_by(Challenge.order_position).all()
    resources_by_order = get_resources_by_order()

    result = []
    for ch in challenges:
        d = {
            "id": ch.id,
            "title": ch.title,
            "description": ch.description,
            "category": ch.category,
            "difficulty": ch.difficulty,
            "total_points": ch.total_points,
            "source_file_path": ch.source_file_path,
            "flags_count": ch.get_flags_count(),
            "resources": resources_by_order.get(ch.order_position, []),
        }
        if user.is_authenticated:
            d["user_progress"] = ch.get_user_progress(db, user.id)
        result.append(d)
    return {"success": True, "challenges": result}


@router.get("/challenges/{challenge_id}")
def get_challenge(request: Request, challenge_id: int):
    db = request.state.db
    user = request.state.user
    ch = db.query(Challenge).get(challenge_id)
    if not ch:
        return JSONResponse({"success": False, "message": "Challenge not found"}, 404)

    d = {
        "id": ch.id,
        "title": ch.title,
        "description": ch.description,
        "category": ch.category,
        "difficulty": ch.difficulty,
        "total_points": ch.total_points,
        "source_file_path": ch.source_file_path,
        "flags_count": ch.get_flags_count(),
        "created_at": ch.created_at.isoformat(),
        "resources": get_resources_by_order().get(ch.order_position, []),
    }
    if user.is_authenticated:
        d["user_progress"] = ch.get_user_progress(db, user.id)
    return {"success": True, "challenge": d}


@router.get("/challenges/{challenge_id}/status")
def get_challenge_status(request: Request, challenge_id: int):
    user = request.state.user
    if not user.is_authenticated:
        return JSONResponse({"success": False, "message": "Login required"}, 401)
    db = request.state.db
    ch = db.query(Challenge).get(challenge_id)
    if not ch:
        return JSONResponse({"success": False, "message": "Challenge not found"}, 404)
    return {"success": True, "progress": ch.get_user_progress(db, user.id)}


# ── Leaderboard ──────────────────────────────────────────────────────────────

@router.get("/leaderboard")
def get_leaderboard(request: Request):
    db = request.state.db
    user = request.state.user
    config = get_site_config(db)
    is_public = config.leaderboard_public
    is_admin_viewer = user.is_authenticated and user.is_admin

    if not config.event_active and not is_admin_viewer:
        return JSONResponse({"success": False, "message": "Event is not active. Leaderboard is frozen."}, 403)

    if not is_public and not is_admin_viewer:
        return JSONResponse({"success": False, "message": "Leaderboard is private"}, 403)

    users = (
        db.query(User)
        .filter(User.is_admin == False, User.is_evaluator == False)
        .all()
    )
    # Compute actual points and last correct submission time
    scored = []
    for u in users:
        pts = u.get_total_points(db)
        last_time = u.get_last_correct_submission_time(db)
        # Keep cached column in sync
        if u.total_points != pts:
            u.total_points = pts
        scored.append((u, pts, last_time))
    # Sort: highest points first; on tie, earlier last-submission time wins
    scored.sort(key=lambda x: (-x[1], x[2] or datetime.max))
    scored = scored[:100]
    db.commit()

    lb = []
    for rank, (u, pts, last_time) in enumerate(scored, 1):
        # Format time with millisecond precision
        if last_time:
            time_str = last_time.strftime("%Y-%m-%dT%H:%M:%S") + ".{:03d}Z".format(int(last_time.microsecond / 1000))
        else:
            time_str = None
        lb.append(
            {
                "rank": rank,
                "username": u.username,
                "total_points": pts,
                "challenges_completed": len(u.get_completed_challenges(db)),
                "joined_at": u.created_at.isoformat(),
                "last_submission_at": time_str,
            }
        )
    return {"success": True, "leaderboard": lb}


# ── User stats ───────────────────────────────────────────────────────────────

@router.get("/user/{user_id}/stats")
def get_user_stats(request: Request, user_id: int):
    db = request.state.db
    u = db.query(User).get(user_id)
    if not u:
        return JSONResponse({"success": False, "message": "User not found"}, 404)
    completed = u.get_completed_challenges(db)
    details = []
    for ct in completed:
        ch = db.query(Challenge).get(ct[0])
        if ch:
            details.append({"challenge_id": ch.id, "title": ch.title, "progress": ch.get_user_progress(db, u.id)})
    return {
        "success": True,
        "user": {
            "id": u.id,
            "username": u.username,
            "total_points": u.total_points,
            "challenges_completed": len(completed),
            "joined_at": u.created_at.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "completed_challenges": details,
        },
    }


# ── File downloads ───────────────────────────────────────────────────────────

@router.get("/challenges/{challenge_id}/download", name="api.download_challenge_file")
def download_challenge_file(request: Request, challenge_id: int):
    db = request.state.db
    ch = db.query(Challenge).get(challenge_id)
    if not ch:
        return JSONResponse({"success": False, "message": "Challenge not found"}, 404)
    resources = get_resources_by_order().get(ch.order_position, [])
    if not resources:
        return JSONResponse({"success": False, "message": "No file available for download"}, 404)
    return _download_resource(request, challenge_id, resources[0]["local_name"])


@router.get("/challenges/{challenge_id}/download/{filename:path}", name="api.download_challenge_resource")
def download_challenge_resource(request: Request, challenge_id: int, filename: str):
    return _download_resource(request, challenge_id, filename)


def _download_resource(request: Request, challenge_id: int, filename: str):
    user = request.state.user
    if not user.is_authenticated:
        return JSONResponse({"success": False, "message": "Login required to download files"}, 401)
    db = request.state.db
    ch = db.query(Challenge).get(challenge_id)
    if not ch:
        return JSONResponse({"success": False, "message": "Challenge not found"}, 404)

    allowed = {
        item["local_name"]: item["display_name"]
        for item in get_resources_by_order().get(ch.order_position, [])
    }
    safe_name = os.path.basename(filename)
    if safe_name not in allowed:
        return JSONResponse({"success": False, "message": "Resource not allowed for this challenge"}, 404)

    file_path = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.exists(file_path):
        return JSONResponse({"success": False, "message": "File not found"}, 404)

    return FileResponse(file_path, filename=allowed[safe_name], media_type="application/octet-stream")
