import uuid
from datetime import datetime

from db import db

class ExtractionJob(db.Model):
    __tablename__ = "extraction_jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = db.Column(db.String(20), nullable=False, default="pending")
    total_matches = db.Column(db.Integer, nullable=False, default=0)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "job_id": self.id,
            "status": self.status,
            "total_matches": self.total_matches,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }