"""Application configuration and evaluation dataset paths."""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROUND_DIR = os.path.dirname(BASE_DIR)  # Yugam_ML_Challenge-3/

# ── App settings ──────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "challenge_files")
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB

# ── Admin defaults ────────────────────────────────────────────────────────────
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@mlctf.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")

# ── Evaluation dataset paths ─────────────────────────────────────────────────
CHALLENGE_1_ORIGINAL_CSV = os.path.join(ROUND_DIR, "Challenge-1", "gatekeeper_dataset.csv")
CHALLENGE_2_ORIGINAL_CSV = os.path.join(ROUND_DIR, "Challenge-2", "gatekeeper_dataset.csv")
CHALLENGE_3_DATASET = os.path.join(ROUND_DIR, "Challenge-3", "gatekeeper_dataset.csv")
CHALLENGE_4_DATASET = os.path.join(ROUND_DIR, "Challenge-4", "bank.csv")
CHALLENGE_4_AUC_THRESHOLD = 0.85
CHALLENGE_5_DATASET = os.path.join(ROUND_DIR, "Challenge-5", "dataset.csv")
