import json
import uuid
from datetime import datetime
from app.extensions import db

class TestRun(db.Model):
    __tablename__ = "test_runs"
    __test__ = False

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    run_type = db.Column(db.String(50), default="exploration")  # exploration, test_execution
    trigger = db.Column(db.String(50), default="manual")        # manual, scheduled, webhook
    status = db.Column(db.String(50), default="queued")         # queued, running, completed, failed, cancelled
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    summary_stats_json = db.Column(db.Text, nullable=True)     # JSON: passed, failed, total, etc.
    error_message = db.Column(db.Text, nullable=True)
    run_dir = db.Column(db.String(255), nullable=True)          # Relative path inside workspace

    # Relationships
    logs = db.relationship(
        "RunLog",
        backref="test_run",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="RunLog.timestamp",
    )

    def get_summary_stats(self) -> dict:
        if not self.summary_stats_json:
            return {}
        try:
            return json.loads(self.summary_stats_json)
        except Exception:
            return {}

    def set_summary_stats(self, stats: dict):
        self.summary_stats_json = json.dumps(stats or {})

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "run_type": self.run_type,
            "trigger": self.trigger,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "summary_stats": self.get_summary_stats(),
            "error_message": self.error_message,
            "run_dir": self.run_dir,
        }

class RunLog(db.Model):
    __tablename__ = "run_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    run_id = db.Column(db.String(36), db.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(20), default="INFO")  # DEBUG, INFO, WARN, ERROR
    message = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        metadata = None
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
            except Exception:
                metadata = self.metadata_json
        return {
            "id": self.id,
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "level": self.level,
            "message": self.message,
            "metadata": metadata,
        }
