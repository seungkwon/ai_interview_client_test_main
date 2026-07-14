from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.job_category import JobCategoryResponse
from app.services.job_category_service import JobCategoryService

router = APIRouter()
job_category_service = JobCategoryService()


@router.get("", response_model=list[JobCategoryResponse])
async def list_job_categories(db: Session = Depends(get_db)) -> list[JobCategoryResponse]:
    return job_category_service.list_categories(db)
