import uuid
from datetime import datetime
from app.extensions import db

class HealerAttempt(db.Model):
    """
    One record per Healer sub-agent invocation against a failing TestCase. The final pipeline
    report's "healer actions taken" section is built directly from these rows.
    """
    __tablename__ = "healer_attempts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_run_id = db.Column(db.String(36), db.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id = db.Column(db.String(36), db.ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    attempt_number = db.Column(db.Integer, default=1)

    classification = db.Column(db.String(50), nullable=True)   # script_bug, app_defect, unknown
    action_taken = db.Column(db.String(50), nullable=True)     # repaired_script, recommended_fix, escalated
    recommendation_text = db.Column(db.Text, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    resolved = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    test_case = db.relationship("TestCase", backref="healer_attempts", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pipeline_run_id": self.pipeline_run_id,
            "test_case_id": self.test_case_id,
            "test_case_title": self.test_case.title if self.test_case else None,
            "attempt_number": self.attempt_number,
            "classification": self.classification,
            "action_taken": self.action_taken,
            "recommendation_text": self.recommendation_text,
            "confidence": self.confidence,
            "resolved": self.resolved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
