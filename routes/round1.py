"""Round 1 — placeholder page (content coming soon)."""

from fastapi import APIRouter, Request

from deps import render

router = APIRouter(prefix="/round1", tags=["round1"])


@router.get("/", name="round1.index")
def round1_page(request: Request):
    """Render the Round 1 placeholder page."""
    return render("round1.html", request)
