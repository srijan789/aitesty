import json
import uuid
from datetime import datetime
from app.extensions import db

class TestPlan(db.Model):
    __tablename__ = "test_plans"
    __test__ = False

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(50), default="active")  # draft, active, archived
    summary = db.Column(db.Text, nullable=True)
    raw_markdown = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    test_cases = db.relationship(
        "TestCase",
        backref="test_plan",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="TestCase.execution_order",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "version": self.version,
            "status": self.status,
            "summary": self.summary,
            "raw_markdown": self.raw_markdown,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "scenarios": [tc.to_dict() for tc in self.test_cases],
        }

class TestCase(db.Model):
    __tablename__ = "test_cases"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_plan_id = db.Column(db.String(36), db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default="happy_path")  # happy_path, edge_case, error_flow
    description = db.Column(db.Text, nullable=True)
    steps_json = db.Column(db.Text, nullable=True)  # JSON list of action steps
    expected_result = db.Column(db.Text, nullable=True)
    script_path = db.Column(db.String(255), nullable=True)  # relative to workspace/tests/
    status = db.Column(db.String(50), default="pending")    # pending, automated, manual
    execution_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_steps(self) -> list:
        if not self.steps_json:
            return []
        try:
            return json.loads(self.steps_json)
        except Exception:
            return []

    def set_steps(self, steps: list):
        self.steps_json = json.dumps(steps or [])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "test_plan_id": self.test_plan_id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "steps": self.get_steps(),
            "expected_result": self.expected_result,
            "script_path": self.script_path,
            "status": self.status,
            "execution_order": self.execution_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
