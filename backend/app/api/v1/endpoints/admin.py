from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.deps import get_db
from app.schemas.admin import (
    ActiveSessionItem,
    AdminInterviewDetail,
    AdminOverview,
    MetricsTimeseriesResponse,
)
from app.services.admin.service import AdminService

router = APIRouter()
admin_service = AdminService()


@router.get("/overview", response_model=AdminOverview)
async def overview(
    _: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminOverview:
    return admin_service.overview(db)


@router.get("/sessions/active", response_model=list[ActiveSessionItem])
async def active_sessions(
    _: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ActiveSessionItem]:
    return admin_service.active_sessions(db)


@router.get("/metrics/timeseries", response_model=MetricsTimeseriesResponse)
async def metrics_timeseries(
    from_at: str = Query(..., alias="from"),
    to_at: str = Query(..., alias="to"),
    interval: str = Query(default="5m"),
    _: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MetricsTimeseriesResponse:
    return admin_service.metrics_timeseries(from_at=from_at, to_at=to_at, interval=interval, db=db)


@router.get("/interviews/{session_id}", response_model=AdminInterviewDetail)
async def interview_detail(
    session_id: str,
    _: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminInterviewDetail:
    return admin_service.interview_detail(session_id, db)
