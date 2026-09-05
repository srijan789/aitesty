import json
import uuid
from datetime import datetime
from app.extensions import db

class PipelineRun(db.Model):
    """
    Owns one full autonomous run of the Plan -> Evaluate -> Generate -> Execute -> Heal -> Report
    pipeline for a project. Individual stages are recorded as TestRun rows tagged with
    pipeline_run_id, so the existing per-run log streaming / UI keeps working unchanged.
    """
    __tablename__ = "pipeline_runs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = db.Column(db.String(50), default="queued")  # queued, running, completed, failed, cancelled
    current_stage = db.Column(db.String(50), nullable=True)  # planning, coverage_check, generation, execution, healing, reporting, done
    trigger = db.Column(db.String(50), default="manual")

    replan_count = db.Column(db.Integer, default=0)
    max_replan_cycles = db.Column(db.Integer, default=2)
    max_heal_attempts = db.Column(db.Integer, default=3)

    product_requirements = db.Column(db.Text, nullable=True)
    natural_language_intent = db.Column(db.Text, nullable=True)

    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)

    final_report_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    stage_runs = db.relationship(
        "TestRun",
        backref="pipeline_run",
        lazy=True,
        order_by="TestRun.started_at",
    )
    healer_attempts = db.relationship(
        "HealerAttempt",
        backref="pipeline_run",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="HealerAttempt.created_at",
    )

    def get_final_report(self) -> dict:
        if not self.final_report_json:
            return {}
        try:
            return json.loads(self.final_report_json)
        except Exception:
            return {}

    def set_final_report(self, report: dict):
        self.final_report_json = json.dumps(report or {})

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "current_stage": self.current_stage,
            "trigger": self.trigger,
            "replan_count": self.replan_count,
            "max_replan_cycles": self.max_replan_cycles,
            "max_heal_attempts": self.max_heal_attempts,
            "product_requirements": self.product_requirements,
            "natural_language_intent": self.natural_language_intent,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "stage_runs": [run.to_dict() for run in self.stage_runs],
        }
