from pydantic import BaseModel


class JobCategoryResponse(BaseModel):
    code: str
    name_ko: str
