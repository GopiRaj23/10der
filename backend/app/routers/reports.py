import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Report, User
from ..schemas import ReportGenerateRequest, ReportOut
from ..services.report_service import generate_report

router = APIRouter(prefix="/reports", tags=["reports"])

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("", response_model=list[ReportOut])
def list_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Report).where(Report.user_id == user.id)
        .order_by(Report.generated_at.desc()).limit(50)
    ).all()


@router.post("/generate", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportGenerateRequest,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filters = {k: v for k, v in {
        "portal_code": payload.portal_code,
        "category": payload.category,
        "state": payload.state,
        "min_score": payload.min_score,
    }.items() if v is not None}
    try:
        report = generate_report(
            db, user,
            report_type=payload.report_type,
            file_format=payload.file_format,
            date_from=payload.date_from,
            date_to=payload.date_to,
            filters=filters,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return report


@router.get("/{report_id}/download")
def download_report(report_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status.HTTP_410_GONE, "Report file no longer available")
    return FileResponse(
        report.file_path,
        media_type=_MEDIA_TYPES.get(report.file_format, "application/octet-stream"),
        filename=os.path.basename(report.file_path),
    )
