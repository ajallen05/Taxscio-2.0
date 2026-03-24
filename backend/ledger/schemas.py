from typing import Optional
from pydantic import BaseModel

class DocumentCreate(BaseModel):
    client_name: str
    document_type: str
    provider: str
    description: str
    source: str
    tax_year: int
    stage: Optional[str] = "Document Submission"
    status: str = "RECEIVED"
    cpa: Optional[str] = None
    due_date: Optional[str] = None
    confidence_score: Optional[float] = None
    extraction_data: Optional[dict] = None
    validation_data: Optional[dict] = None
    content_data: Optional[dict] = None
    
    class Config:
        arbitrary_types_allowed = True

