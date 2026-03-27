from sqlalchemy import Column, Integer, String, Text, JSON, Float, Index
from .database import Base

class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True)
    document_id = Column(String, unique=True)
    client_id   = Column(String, nullable=True, index=True)   # FK → clients.id (cross-db reference)
    client_name = Column(String)
    document_type = Column(String)
    provider = Column(String)
    description = Column(Text)
    source = Column(String)
    tax_year = Column(Integer)
    stage = Column(String)
    status = Column(String)
    version = Column(Integer)
    upload_count = Column(Integer, default=1)
    content_hash = Column(String)
    extraction_json_path = Column(String, nullable=True)  # relative path to local_extraction/<id>.json
    audit_trail = Column(JSON)
    cpa = Column(String)
    due_date = Column(String)
    confidence_score = Column(Float)


class DocumentLog(Base):
    __tablename__ = "document_logs"
    id = Column(Integer, primary_key=True)
    document_id = Column(String)
    version = Column(Integer)
    upload_count = Column(Integer, default=1)
    content_hash = Column(String)
    client_id   = Column(String, nullable=True)   # FK → clients.id (cross-db reference)
    client_name = Column(String)
    document_type = Column(String)
    provider = Column(String)
    description = Column(Text)
    source = Column(String)
    tax_year = Column(Integer)
    stage = Column(String)
    status = Column(String)
    extraction_json_path = Column(String, nullable=True)  # relative path to local_extraction/<id>.json
    cpa = Column(String)
    due_date = Column(String)
    confidence_score = Column(Float)
