"""Round 2 page — exposes Yugam ML Challenge 2 files for download.

Files are only accessible when the admin has set active_round >= 2.
"""

import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from deps import render
from models import get_site_config

router = APIRouter(prefix="/round2", tags=["round2"])


def _round2_allowed(request: Request) -> bool:
    """Return True if Round 2 content should be visible to this user."""
    user = getattr(request.state, "user", None)
    if user and getattr(user, "is_admin", False):
        return True
    config = getattr(request.state, "site_config", None)
    if config and config.active_round >= 2:
        return True
    return False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUND2_DIR = os.path.join(BASE_DIR, "static", "round2_files")

ROUND2_FILES = [
    {
        "name": "ml_debug_classification_final.ipynb",
        "display": "Classification Notebook",
        "description": "Debug the classification pipeline — find and fix all bugs.",
        "icon": "📓",
    },
    {
        "name": "ml_debug_regression_final.ipynb",
        "display": "Regression Notebook",
        "description": "Debug the regression pipeline — find and fix all bugs.",
        "icon": "📓",
    },
    {
        "name": "titanic_data.csv",
        "display": "Titanic Dataset",
        "description": "CSV dataset used by the classification notebook.",
        "icon": "📊",
    },
    {
        "name": "requirements.txt",
        "display": "Requirements",
        "description": "Python dependencies for Round 2.",
        "icon": "📄",
    },
    {
        "name": "setup.bat",
        "display": "Setup Script",
        "description": "Windows batch script to set up the environment.",
        "icon": "⚙️",
    },
]


@router.get("/", name="round2.index")
def round2_page(request: Request):
    """Render the Round 2 landing page with download links."""
    if not _round2_allowed(request):
        return RedirectResponse(url="/", status_code=303)
    files = []
    for f in ROUND2_FILES:
        fpath = os.path.join(ROUND2_DIR, f["name"])
        size_bytes = os.path.getsize(fpath) if os.path.exists(fpath) else 0
        if size_bytes > 1_048_576:
            size_str = f"{size_bytes / 1_048_576:.1f} MB"
        elif size_bytes > 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes} B"
        files.append({**f, "size": size_str, "exists": os.path.exists(fpath)})
    return render("round2.html", request, files=files)


@router.get("/download/{filename}", name="round2.download")
def download_round2_file(request: Request, filename: str):
    """Serve a Round 2 file for download."""
    if not _round2_allowed(request):
        return RedirectResponse(url="/", status_code=303)
    # Only allow known filenames
    allowed = {f["name"] for f in ROUND2_FILES}
    if filename not in allowed:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "File not found"}, status_code=404)

    fpath = os.path.join(ROUND2_DIR, filename)
    if not os.path.exists(fpath):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "File not found"}, status_code=404)

    return FileResponse(fpath, filename=filename, media_type="application/octet-stream")
