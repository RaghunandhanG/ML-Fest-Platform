"""SQLAlchemy ORM models (plain SQLAlchemy — no Flask dependency)."""

from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint, func, distinct,
)
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re

from database import Base


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    total_points = Column(Integer, default=0)
    is_admin = Column(Boolean, default=False)
    is_evaluator = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    is_leaderboard_public = Column(Boolean, default=False)
    event_active = Column(Boolean, default=False)
    assigned_evaluator_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Self-referential: evaluator (parent) ← participant (child)
    # assigned_evaluator: the evaluator this user is assigned to (many-to-one)
    # assigned_participants: participants assigned to this evaluator (one-to-many)
    assigned_evaluator_rel = relationship(
        "User",
        foreign_keys=[assigned_evaluator_id],
        remote_side="User.id",
        backref="assigned_participants",
    )

    @property
    def assigned_evaluator(self):
        return self.assigned_evaluator_rel

    # Runtime attribute (not a DB column) — mimics Flask-Login's UserMixin
    is_authenticated = True

    submissions = relationship(
        "Submission", backref="user", lazy=True,
        cascade="all, delete-orphan", foreign_keys="Submission.user_id",
    )
    scores = relationship(
        "Score", foreign_keys="Score.user_id", backref="user",
        lazy=True, cascade="all, delete-orphan",
    )
    approved_scores = relationship(
        "Score", foreign_keys="Score.approved_by",
        backref="approved_by_user", lazy=True,
    )

    # ── helpers ───────────────────────────────────────────────────────────
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_total_points(self, db):
        return (
            db.query(func.sum(Score.points))
            .filter(Score.user_id == self.id, Score.is_approved == True)
            .scalar()
            or 0
        )

    def get_completed_challenges(self, db):
        return (
            db.query(distinct(Submission.challenge_id))
            .filter(Submission.user_id == self.id, Submission.is_correct == True)
            .all()
        )

    def __repr__(self):
        return f"<User {self.username}>"


# ── Challenge ─────────────────────────────────────────────────────────────────

class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100))
    difficulty = Column(String(50))
    total_points = Column(Integer, default=100)
    source_file_path = Column(String(255))
    order_position = Column(Integer, default=0)
    is_revealed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    flags = relationship("Flag", backref="challenge", lazy=True, cascade="all, delete-orphan")
    submissions = relationship("Submission", backref="challenge", lazy=True, cascade="all, delete-orphan")
    scores = relationship("Score", backref="challenge", lazy=True, cascade="all, delete-orphan")

    @property
    def flags_count(self):
        return len(self.flags)

    def get_flags_count(self):
        return len(self.flags)

    def get_user_progress(self, db, user_id):
        approved_flags = (
            db.query(func.count(distinct(Score.flag_id)))
            .filter(Score.user_id == user_id, Score.challenge_id == self.id, Score.is_approved == True)
            .scalar()
            or 0
        )
        pending_flags = (
            db.query(func.count(distinct(Score.flag_id)))
            .filter(Score.user_id == user_id, Score.challenge_id == self.id, Score.is_approved == False)
            .scalar()
            or 0
        )
        total_points = (
            db.query(func.sum(Score.points))
            .filter(Score.user_id == user_id, Score.challenge_id == self.id, Score.is_approved == True)
            .scalar()
            or 0
        )
        return {
            "completed_flags": approved_flags,
            "pending_flags": pending_flags,
            "total_flags": len(self.flags),
            "points_earned": total_points,
            "total_possible": self.total_points,
        }

    def __repr__(self):
        return f"<Challenge {self.title}>"


# ── Flag ──────────────────────────────────────────────────────────────────────

class Flag(Base):
    __tablename__ = "flags"

    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    flag_content = Column(String(255), nullable=False)
    flag_order = Column(Integer)
    points_value = Column(Integer, default=25)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    submissions = relationship("Submission", backref="flag", lazy=True)

    def validate_flag(self, submitted_flag):
        if self.flag_content.lower() == submitted_flag.lower():
            return True
        if self.flag_content.startswith("REGEX:"):
            pattern = self.flag_content.replace("REGEX:", "")
            try:
                if re.match(pattern, submitted_flag):
                    return True
            except re.error:
                pass
        return False

    def __repr__(self):
        return f"<Flag challenge_id={self.challenge_id} order={self.flag_order}>"


# ── Submission ────────────────────────────────────────────────────────────────

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    flag_id = Column(Integer, ForeignKey("flags.id"))
    submitted_flag = Column(String(255), nullable=False)
    is_correct = Column(Boolean, default=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    points_awarded = Column(Integer, default=0)

    def __repr__(self):
        return f"<Submission user={self.user_id} challenge={self.challenge_id} correct={self.is_correct}>"


# ── Score ─────────────────────────────────────────────────────────────────────

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    flag_id = Column(Integer, ForeignKey("flags.id"), nullable=False)
    points = Column(Integer, nullable=False)
    flag_points = Column(Integer, default=0)
    explanation_points = Column(Integer, default=0)
    is_approved = Column(Boolean, default=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    awarded_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    leaderboard_visible = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("user_id", "flag_id", name="user_flag_unique"),)

    def __repr__(self):
        return f"<Score user={self.user_id} flag={self.flag_id} pts={self.points} approved={self.is_approved}>"
