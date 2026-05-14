import uuid
from datetime import datetime

from db import db


class ExtractionJob(db.Model):
    __tablename__ = "extraction_jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = db.Column(db.String(20), nullable=False, default="pending")
    total_matches = db.Column(db.Integer, nullable=False, default=0)
    error = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "job_id": self.id,
            "status": self.status,
            "total_matches": self.total_matches,
            "error": self.error,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ExtractedFile(db.Model):
    __tablename__ = "extracted_files"

    id = db.Column(db.Integer, primary_key=True)
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