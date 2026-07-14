from pydantic import BaseModel, Field


class RecordedAnalysisCreateResponse(BaseModel):
    session_id: str
    job_id: str
    status: str


class RecordedAnalysisStatusResponse(BaseModel):
    session_id: str
    job_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    file_name: str
    duration_sec: int = Field(ge=0)
    content_type: str
