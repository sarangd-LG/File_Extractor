import uuid
from datetime import datetime

from db import db

class ExtractedFile(db.Model):
    __tablename__ = "extracted_files"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = db.Column(db.String(36), db.ForeignKey("extraction_jobs.id"), nullable=False)
    full_path = db.Column(db.Text, nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    nesting_depth = db.Column(db.Integer, nullable=False)
    extracted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source_archive_name = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "full_path": self.full_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "nesting_depth": self.nesting_depth,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
            "source_archive_name": self.source_archive_name,
        }