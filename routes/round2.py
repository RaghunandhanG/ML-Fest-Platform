"""Round 2 page — exposes Yugam ML Challenge 2 files for download."""

import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from deps import render

router = APIRouter(prefix="/round2", tags=["round2"])

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
