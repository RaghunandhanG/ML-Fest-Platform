"""Round 1 — Timed MCQ quiz (60 questions, 45 minutes).

Flow:
  GET  /round1/         → landing page (description + "Start Test" button)
                           OR quiz page (if already started)
                           OR submitted page (if already done)
  POST /round1/start    → create attempt, redirect to quiz
  POST /round1/save     → save one answer (AJAX)
  POST /round1/tab-switch → record tab switch (AJAX)
  POST /round1/submit   → final submission
"""

import json
import os
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from deps import render, flash
from models import QuizAttempt, get_site_config

router = APIRouter(prefix="/round1", tags=["round1"])

# ── Load questions once at import time ─────────────────────────────────────────
_QUESTIONS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "round1_questions.json")
with open(_QUESTIONS_PATH, "r", encoding="utf-8") as _f:
    _QUIZ_DATA = json.load(_f)

QUESTIONS = _QUIZ_DATA["questions"]
DURATION_MINUTES = _QUIZ_DATA["duration_minutes"]
MAX_TAB_SWITCHES = _QUIZ_DATA["max_tab_switches"]
POINTS_PER_Q = _QUIZ_DATA.get("points_per_question", 1)


def _round1_allowed(request: Request) -> bool:
    """Return True if Round 1 content should be visible."""
    user = getattr(request.state, "user", None)
    if user and getattr(user, "is_admin", False):
        return True
    config = getattr(request.state, "site_config", None)
    if config and config.active_round >= 1:
        return True
    return False


def _get_shuffled_order(user_id: int):
    """Return a deterministic-per-user shuffled list of question indices."""
    indices = list(range(len(QUESTIONS)))
    rng = random.Random(user_id * 9973)
    rng.shuffle(indices)
    return indices


def _compute_score(attempt: QuizAttempt) -> int:
    """Score the attempt against correct answers."""
    answers = json.loads(attempt.answers)
    order = json.loads(attempt.question_order)
    score = 0
    for idx_str, selected in answers.items():
        q_idx = order[int(idx_str)]
        correct = QUESTIONS[q_idx]["answer"]
        if selected == correct:
            score += POINTS_PER_Q
    return score


def _time_remaining(attempt: QuizAttempt) -> int:
    """Seconds remaining for this attempt. Returns 0 if expired."""
    if attempt.is_submitted:
        return 0
    deadline = attempt.started_at + timedelta(minutes=DURATION_MINUTES)
    remaining = (deadline - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))


def _auto_submit_if_expired(attempt, db):
    """If time has expired, auto-submit and return True."""
    if attempt.is_submitted:
        return True
    if _time_remaining(attempt) <= 0:
        attempt.is_submitted = True
        attempt.finished_at = datetime.utcnow()
        attempt.score = _compute_score(attempt)
        db.commit()
        return True
    return False


# ── Page: GET /round1/ ────────────────────────────────────────────────────────

@router.get("/", name="round1.index")
def round1_page(request: Request):
    """
    Three states:
      1. No attempt → show landing page with description + "Start Test"
      2. Attempt in progress → show quiz
      3. Attempt submitted → show confirmation
    """
    user = getattr(request.state, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return render("round1.html", request,
                       state="login_required",
                       total_questions=len(QUESTIONS),
                       duration_minutes=DURATION_MINUTES,
                       max_tab_switches=MAX_TAB_SWITCHES)
    if not _round1_allowed(request):
        flash(request, "Round 1 is not active yet.", "warning")
        return RedirectResponse(url="/", status_code=303)

    db = request.state.db
    attempt = db.query(QuizAttempt).filter_by(user_id=user.id).first()

    # ── State 1: no attempt → landing page ────────────────────────────────
    if attempt is None:
        return render("round1.html", request,
                       state="landing",
                       total_questions=len(QUESTIONS),
                       duration_minutes=DURATION_MINUTES,
                       max_tab_switches=MAX_TAB_SWITCHES)

    # ── State 3: already submitted ────────────────────────────────────────
    if _auto_submit_if_expired(attempt, db):
        return render("round1.html", request,
                       state="submitted",
                       total_questions=len(QUESTIONS))

    # ── State 2: quiz in progress ─────────────────────────────────────────
    remaining = _time_remaining(attempt)
    order = json.loads(attempt.question_order)
    answers = json.loads(attempt.answers)
    quiz_questions = []
    for pos, q_idx in enumerate(order):
        q = QUESTIONS[q_idx]
        quiz_questions.append({
            "pos": pos,
            "question": q["question"],
            "options": q["options"],
        })

    return render("round1.html", request,
                   state="quiz",
                   quiz_questions=quiz_questions,
                   answers=answers,
                   time_remaining=remaining,
                   tab_switches=attempt.tab_switches,
                   max_tab_switches=MAX_TAB_SWITCHES,
                   total_questions=len(QUESTIONS))


# ── POST /round1/start — begin the quiz ──────────────────────────────────────

@router.post("/start", name="round1.start")
def start_quiz(request: Request):
    """Create a new quiz attempt and redirect to the quiz page."""
    user = getattr(request.state, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if not _round1_allowed(request):
        flash(request, "Round 1 is not active yet.", "warning")
        return RedirectResponse(url="/", status_code=303)

    db = request.state.db
    existing = db.query(QuizAttempt).filter_by(user_id=user.id).first()
    if existing:
        # Already started — just go to the quiz
        return RedirectResponse(url="/round1/", status_code=303)

    order = _get_shuffled_order(user.id)
    attempt = QuizAttempt(
        user_id=user.id,
        question_order=json.dumps(order),
        answers="{}",
        started_at=datetime.utcnow(),
    )
    db.add(attempt)
    db.commit()

    return RedirectResponse(url="/round1/", status_code=303)


# ── AJAX: POST /round1/save ──────────────────────────────────────────────────

@router.post("/save", name="round1.save")
async def save_answer(request: Request):
    """Save a single answer (AJAX). Body: {pos: int, selected: int}"""
    body = await request.json()

    user = getattr(request.state, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = request.state.db
    attempt = db.query(QuizAttempt).filter_by(user_id=user.id).first()
    if not attempt or attempt.is_submitted:
        return JSONResponse({"error": "Quiz already submitted or not started"}, status_code=400)
    if _time_remaining(attempt) <= 0:
        attempt.is_submitted = True
        attempt.finished_at = datetime.utcnow()
        attempt.score = _compute_score(attempt)
        db.commit()
        return JSONResponse({"error": "Time expired", "auto_submitted": True}, status_code=400)

    pos = body.get("pos")
    selected = body.get("selected")
    if pos is None or selected is None:
        return JSONResponse({"error": "Missing pos or selected"}, status_code=400)

    answers = json.loads(attempt.answers)
    answers[str(pos)] = int(selected)
    attempt.answers = json.dumps(answers)
    db.commit()

    return JSONResponse({"ok": True, "answered": len(answers)})


# ── AJAX: POST /round1/tab-switch ────────────────────────────────────────────

@router.post("/tab-switch", name="round1.tab_switch")
def record_tab_switch(request: Request):
    """Record a tab switch. Auto-submit on reaching max."""
    user = getattr(request.state, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = request.state.db
    attempt = db.query(QuizAttempt).filter_by(user_id=user.id).first()
    if not attempt or attempt.is_submitted:
        return JSONResponse({"error": "Already submitted"}, status_code=400)

    attempt.tab_switches += 1
    auto_submitted = False

    if attempt.tab_switches >= MAX_TAB_SWITCHES:
        attempt.is_submitted = True
        attempt.finished_at = datetime.utcnow()
        attempt.score = _compute_score(attempt)
        auto_submitted = True

    db.commit()
    return JSONResponse({
        "tab_switches": attempt.tab_switches,
        "max": MAX_TAB_SWITCHES,
        "auto_submitted": auto_submitted,
    })


# ── POST /round1/submit ──────────────────────────────────────────────────────

@router.post("/submit", name="round1.submit")
def submit_quiz(request: Request):
    """Submit the quiz. All questions must be answered."""
    user = getattr(request.state, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = request.state.db
    attempt = db.query(QuizAttempt).filter_by(user_id=user.id).first()
    if not attempt:
        flash(request, "No quiz attempt found.", "danger")
        return RedirectResponse(url="/round1/", status_code=303)
    if attempt.is_submitted:
        flash(request, "Quiz already submitted.", "info")
        return RedirectResponse(url="/round1/", status_code=303)

    answers = json.loads(attempt.answers)
    if len(answers) < len(QUESTIONS):
        flash(request, f"Please answer all {len(QUESTIONS)} questions before submitting. You've answered {len(answers)}.", "warning")
        return RedirectResponse(url="/round1/", status_code=303)

    attempt.is_submitted = True
    attempt.finished_at = datetime.utcnow()
    attempt.score = _compute_score(attempt)
    db.commit()

    flash(request, "Quiz submitted successfully!", "success")
    return RedirectResponse(url="/round1/", status_code=303)

