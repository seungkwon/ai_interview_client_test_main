from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import JobCategory
from app.schemas.job_category import JobCategoryResponse

JOB_CATEGORIES = [
    {"code": "management_hr", "name_ko": "경영/인사"},
    {"code": "accounting", "name_ko": "회계"},
    {"code": "it", "name_ko": "IT"},
    {"code": "rnd", "name_ko": "R&D"},
    {"code": "manufacturing", "name_ko": "제조"},
    {"code": "distribution", "name_ko": "유통"},
    {"code": "public", "name_ko": "공공"},
    {"code": "general_office", "name_ko": "일반 사무"},
]


class JobCategoryService:
    def list_categories(self, db: Session | None = None) -> list[JobCategoryResponse]:
        if db is not None:
            try:
                categories = db.scalars(
                    select(JobCategory)
                    .where(JobCategory.is_active.is_(True))
                    .order_by(JobCategory.sort_order.asc(), JobCategory.id.asc())
                ).all()
                if categories:
                    return [
                        JobCategoryResponse(code=item.code, name_ko=item.name_ko)
                        for item in categories
                    ]
            except SQLAlchemyError:
                db.rollback()

        return [JobCategoryResponse(**item) for item in JOB_CATEGORIES]
