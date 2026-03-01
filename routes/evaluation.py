"""
Challenge evaluation endpoints (ported from the standalone evaluation_api).

All endpoints live at /challenge-{1..5} and automatically judge submissions.
If a valid username is supplied via the `username` form field, the user's
personalised flag (from the UserFlag table) is returned on success.
"""

import io
from typing import Optional

import pandas as pd
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from sklearn.linear_model import LogisticRegression
from sqlalchemy.orm import Session

from deps import get_db
from models import User, Challenge, Flag, UserFlag
from config import (
    CHALLENGE_1_ORIGINAL_CSV,
    CHALLENGE_2_ORIGINAL_CSV,
    CHALLENGE_3_DATASET,
    CHALLENGE_4_DATASET,
    CHALLENGE_4_AUC_THRESHOLD,
    CHALLENGE_5_DATASET,
)

router = APIRouter(tags=["evaluation"])

FEATURE_COLS = ["Night_Activity", "Trust_Index", "Contribution", "Conflict_Score"]
EXPECTED_COLS = ["ID"] + FEATURE_COLS + ["Label"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_bytes(upload: UploadFile) -> bytes:
    return upload.file.read()


def _get_user_flag(db: Session, username: Optional[str], password: Optional[str], challenge_order: int, static_flag: str) -> str:
    """Return the user's personalised flag, or static_flag if credentials are missing/invalid."""
    if not username or not username.strip():
        return static_flag
    user = db.query(User).filter_by(username=username.strip()).first()
    if not user:
        return static_flag
    challenge = db.query(Challenge).filter_by(order_position=challenge_order).first()
    if not challenge:
        return static_flag
    flag = db.query(Flag).filter_by(challenge_id=challenge.id, flag_order=1).first()
    if not flag:
        return static_flag
    user_flag = db.query(UserFlag).filter_by(user_id=user.id, flag_id=flag.id).first()
    if not user_flag:
        return static_flag
    return user_flag.flag_value


# ── Challenge 1 — Data Poisoning ─────────────────────────────────────────────

@router.post("/challenge-1", summary="Challenge 1: Data Poisoning")
async def evaluate_challenge_1(
    request: Request,
    file: UploadFile = File(..., description="tampered_data.csv"),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
):
    db = get_db(request)

    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")

    raw = _read_bytes(file)
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        raise HTTPException(400, f"CSV is missing required columns: {missing}")

    X = df[FEATURE_COLS].values
    y = df["Label"].values

    try:
        model = LogisticRegression(max_iter=1000)
        model.fit(X, y)
    except Exception as e:
        raise HTTPException(500, f"Model training failed: {e}")

    last_row = df[FEATURE_COLS].iloc[[-1]].values
    prediction = int(model.predict(last_row)[0])
    proba = model.predict_proba(last_row)[0]
    confidence = {
        "citizen_confidence": round(float(proba[0]), 4),
        "thief_confidence":   round(float(proba[1]), 4),
    }

    if prediction == 0:
        flag = _get_user_flag(db, username, password, 1, "CTF{p01s0n_th3_w3ll_g4t3_f4lls}")
        return JSONResponse({"result": "success", "flag": flag,
                             "message": "The Gatekeeper has been fooled! The thief is classified as a Citizen.",
                             **confidence})
    return JSONResponse({"result": "failure", "flag": None,
                         "message": "The thief is still correctly identified. The Gatekeeper was not fooled.",
                         **confidence})


# ── Challenge 2 — Constrained Data Poisoning ─────────────────────────────────

@router.post("/challenge-2", summary="Challenge 2: Constrained Data Poisoning")
async def evaluate_challenge_2(
    request: Request,
    file: UploadFile = File(..., description="tampered_data.csv"),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
):
    db = get_db(request)

    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")

    raw = _read_bytes(file)
    try:
        submitted = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    missing = [c for c in EXPECTED_COLS if c not in submitted.columns]
    if missing:
        raise HTTPException(400, f"CSV is missing required columns: {missing}")

    try:
        original = pd.read_csv(CHALLENGE_2_ORIGINAL_CSV)
    except FileNotFoundError:
        raise HTTPException(500, "Reference dataset not found on the server. Contact the organiser.")

    if len(submitted) != len(original):
        return JSONResponse({"result": "failure", "flag": None,
                             "message": "Row count does not match the original dataset."})

    last_orig = original.iloc[-1][FEATURE_COLS + ["Label"]].reset_index(drop=True)
    last_sub  = submitted.iloc[-1][FEATURE_COLS + ["Label"]].reset_index(drop=True)
    if not last_orig.equals(last_sub):
        return JSONResponse({"result": "failure", "flag": None, "tampering_detected": True,
                             "tampered_location": "last row (ID = 10)",
                             "message": "Tampering detected! The last row (ID = 10) has been modified. Submission rejected."})

    if not original["Label"].reset_index(drop=True).equals(submitted["Label"].reset_index(drop=True)):
        return JSONResponse({"result": "failure", "flag": None, "tampering_detected": True,
                             "tampered_location": "Label column",
                             "message": "Tampering detected! The Label column has been modified. Submission rejected."})

    X = submitted[FEATURE_COLS].values
    y = submitted["Label"].values
    try:
        model = LogisticRegression(max_iter=1000)
        model.fit(X, y)
    except Exception as e:
        raise HTTPException(500, f"Model training failed: {e}")

    last_row   = submitted[FEATURE_COLS].iloc[[-1]].values
    prediction = int(model.predict(last_row)[0])
    proba      = model.predict_proba(last_row)[0]
    confidence = {
        "citizen_confidence": round(float(proba[0]), 4),
        "thief_confidence":   round(float(proba[1]), 4),
    }

    if prediction == 0:
        flag = _get_user_flag(db, username, password, 2, "CTF{sh4d0ws_sl1p_p4st_th3_l0ck3d_g4t3}")
        return JSONResponse({"result": "success", "flag": flag,
                             "message": "The Gatekeeper was fooled again! The thief slipped past undetected.",
                             **confidence})
    return JSONResponse({"result": "failure", "flag": None,
                         "message": "The thief is still correctly identified. The Gatekeeper held its ground.",
                         **confidence})


# ── Challenge 3 — Fix the Corrupted Model ────────────────────────────────────

@router.post("/challenge-3", summary="Challenge 3: Fix the Corrupted Model")
async def evaluate_challenge_3(
    request: Request,
    file: UploadFile = File(..., description="fixed_model.pkl"),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
):
    db = get_db(request)

    if not file.filename.endswith(".pkl"):
        raise HTTPException(400, "Please upload a .pkl model file.")

    raw = _read_bytes(file)
    try:
        import joblib
        submitted_model = joblib.load(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"Could not load model: {e}")

    if not hasattr(submitted_model, "predict"):
        raise HTTPException(400, "Uploaded file does not appear to be a valid scikit-learn model.")

    try:
        df = pd.read_csv(CHALLENGE_3_DATASET)
    except FileNotFoundError:
        raise HTTPException(500, "Reference dataset not found on the server. Contact the organiser.")

    miss = [c for c in FEATURE_COLS + ["Label"] if c not in df.columns]
    if miss:
        raise HTTPException(500, f"Reference dataset is missing columns: {miss}")

    X     = df[FEATURE_COLS].values
    y     = df["Label"].values

    try:
        preds = submitted_model.predict(X)
    except Exception as e:
        raise HTTPException(400, f"Model prediction failed: {e}")

    correct  = int((preds == y).sum())
    total    = len(y)
    accuracy = round(correct / total, 4)

    if accuracy == 1.0:
        flag = _get_user_flag(db, username, password, 3, "CTF{r3wr1t3_th3_m1nd_r3cl41m_th3_g4t3}")
        return JSONResponse({"result": "success", "flag": flag,
                             "message": "The Gatekeeper is fully restored! Every single record is classified correctly.",
                             "accuracy": accuracy})
    return JSONResponse({"result": "failure", "flag": None,
                         "message": f"Not quite. The model correctly classified {correct}/{total} records - accuracy: {accuracy * 100:.1f}%. You need 100%.",
                         "accuracy": accuracy})


# ── Challenge 4 — Fix the Sentinel Training Pipeline ─────────────────────────

@router.post("/challenge-4", summary="Challenge 4: Fix the Sentinel Training Pipeline")
async def evaluate_challenge_4(
    request: Request,
    file: UploadFile = File(..., description="predictions.csv"),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
):
    db = get_db(request)

    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")

    raw = _read_bytes(file)
    try:
        pred_df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    if "prediction" not in pred_df.columns:
        raise HTTPException(400, "CSV must have a column named 'prediction'.")

    y_pred = pred_df["prediction"].values
    if not all((y_pred >= 0) & (y_pred <= 1)):
        raise HTTPException(400, "All prediction values must be probabilities in the range [0, 1].")

    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.model_selection import train_test_split
    import numpy as np

    try:
        df_bank = pd.read_csv(CHALLENGE_4_DATASET, sep=";")
    except FileNotFoundError:
        raise HTTPException(500, "Reference dataset not found on the server. Contact the organiser.")

    df_work = df_bank.copy()
    df_work["y"] = (df_work["y"] == "yes").astype(int)
    cat_cols = df_work.select_dtypes(include="object").columns.tolist()
    le = LabelEncoder()
    for col in cat_cols:
        df_work[col] = le.fit_transform(df_work[col])

    df_yes = df_work[df_work["y"] == 1]
    df_no  = df_work[df_work["y"] == 0].sample(len(df_yes), random_state=42)
    df_bal = pd.concat([df_yes, df_no]).sample(frac=1, random_state=42).reset_index(drop=True)

    X      = df_bal.drop("y", axis=1).values.astype(float)
    y_true = df_bal["y"].values.astype(int)
    scaler = StandardScaler()
    X      = scaler.fit_transform(X)
    _, _, _, y_test = train_test_split(X, y_true, test_size=0.20, random_state=42, stratify=y_true)

    if len(y_pred) != len(y_test):
        return JSONResponse({"result": "failure", "flag": None,
                             "message": f"Row count mismatch: submitted {len(y_pred)} predictions but test set has {len(y_test)} samples."})

    def _auc(y_t, y_s):
        y_t = np.array(y_t, dtype=float)
        y_s = np.array(y_s, dtype=float)
        order = np.argsort(y_s)[::-1]
        y_t_sorted = y_t[order]
        P  = int(y_t.sum()); N = len(y_t) - P
        tpr, fpr = [0.0], [0.0]
        tp = fp = 0
        for label in y_t_sorted:
            if label == 1: tp += 1
            else:          fp += 1
            tpr.append(tp / P); fpr.append(fp / N)
        return round(sum((fpr[i]-fpr[i-1])*(tpr[i]+tpr[i-1])/2 for i in range(1, len(fpr))), 4)

    y_pred_class = (y_pred >= 0.5).astype(int)
    accuracy = round(float((y_pred_class == y_test).mean()), 4)
    auc      = _auc(y_test, y_pred)

    if auc >= CHALLENGE_4_AUC_THRESHOLD:
        flag = _get_user_flag(db, username, password, 4, "CTF{4w4k3n_th3_sl33p1ng_s3nt1n3l}")
        return JSONResponse({"result": "success", "flag": flag,
                             "message": "The Sentinel is awake! Your model generalises well on the test set.",
                             "roc_auc": auc, "accuracy": accuracy})
    return JSONResponse({"result": "failure", "flag": None,
                         "message": f"The Sentinel is still struggling. ROC-AUC: {auc:.4f} (need >= {CHALLENGE_4_AUC_THRESHOLD}). Accuracy: {accuracy:.4f}.",
                         "roc_auc": auc, "accuracy": accuracy})


# ── Challenge 5 — Recover the Model Weights ─────────────────────────────────

@router.post("/challenge-5", summary="Challenge 5: Recover the Model Weights")
async def evaluate_challenge_5(
    request: Request,
    file: UploadFile = File(..., description="model.pkl"),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
):
    db = get_db(request)

    if not file.filename.endswith(".pkl"):
        raise HTTPException(400, "Please upload a .pkl model file.")

    import numpy as np

    raw = _read_bytes(file)
    try:
        import joblib
        submitted_model = joblib.load(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"Could not load model: {e}")

    if not hasattr(submitted_model, "predict"):
        raise HTTPException(400, "Uploaded file does not appear to be a valid scikit-learn model (missing predict method).")

    try:
        df = pd.read_csv(CHALLENGE_5_DATASET)
    except FileNotFoundError:
        raise HTTPException(500, "Reference dataset not found on the server. Contact the organiser.")

    required = ["X1", "X2", "y"]
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise HTTPException(500, f"Reference dataset is missing columns: {miss}")

    X      = df[["X1", "X2"]].values.astype(float)
    y_true = df["y"].values.astype(float)

    try:
        y_pred = submitted_model.predict(X).astype(float)
    except Exception as e:
        raise HTTPException(400, f"Model prediction failed: {e}")

    residuals     = y_true - y_pred
    max_abs_error = float(np.max(np.abs(residuals)))
    mse           = float(np.mean(residuals ** 2))
    ss_res        = float(np.sum(residuals ** 2))
    ss_tot        = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else (1.0 if ss_res == 0 else 0.0)

    weights_info: dict = {}
    if hasattr(submitted_model, "coef_"):
        weights_info["coefficients"] = submitted_model.coef_.tolist()
    if hasattr(submitted_model, "intercept_"):
        weights_info["intercept"] = float(submitted_model.intercept_)

    is_perfect = (r2 == 1.0) and (max_abs_error == 0.0) and (mse == 0.0)

    if is_perfect:
        flag = _get_user_flag(db, username, password, 5, "CTF{w31ght_0f_truth_r3v34l3d}")
        return JSONResponse({"result": "success", "flag": flag,
                             "message": "Perfect fit! You have recovered the exact weights of the original model.",
                             "r2_score": r2, "mse": mse, "max_abs_error": max_abs_error, **weights_info})
    return JSONResponse({"result": "failure", "flag": None,
                         "message": f"Not a perfect fit. R2 = {r2} (need exactly 1.0). Max abs error = {max_abs_error} (need 0). MSE = {mse} (need 0).",
                         "r2_score": r2, "mse": mse, "max_abs_error": max_abs_error, **weights_info})
