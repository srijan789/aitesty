import json
import uuid
from datetime import datetime
from app.extensions import db

class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_url = db.Column(db.String(500), nullable=False)
    auth_type = db.Column(db.String(50), default="none")  # none, form, basic, bearer
    credentials_json = db.Column(db.Text, nullable=True)  # JSON-encoded credentials
    scope_instructions = db.Column(db.Text, nullable=True)
    prd_text = db.Column(db.Text, nullable=True)  # Product Requirement Document / Specification
    crawl_depth = db.Column(db.Integer, default=2, nullable=False)  # Depth of route link exploration (1-5)
    max_pages = db.Column(db.Integer, default=10, nullable=False)  # Maximum unique routes to crawl
    target_test_count = db.Column(db.Integer, default=12, nullable=False)  # Target test scenarios to generate
    exploration_strategy = db.Column(db.String(50), default="balanced", nullable=False)  # balanced, deep_crawl, form_heavy, critical_paths
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    test_plans = db.relationship("TestPlan", backref="project", lazy=True, cascade="all, delete-orphan")
    test_runs = db.relationship("TestRun", backref="project", lazy=True, cascade="all, delete-orphan")

    def get_credentials(self) -> dict:
        if not self.credentials_json:
            return {}
        try:
            return json.loads(self.credentials_json)
        except Exception:
            return {}

    def set_credentials(self, creds: dict):
        self.credentials_json = json.dumps(creds or {})

    def get_masked_credentials(self) -> dict:
        creds = self.get_credentials()
        masked = {}
        for k, v in creds.items():
            val = str(v)
            if any(secret_word in k.lower() for secret_word in ["pass", "token", "secret", "key"]):
                masked[k] = "••••••••" if len(val) > 0 else ""
            else:
                masked[k] = val
        return masked

    @property
    def latest_plan(self):
        from app.models.test_plan import TestPlan
        return (
            TestPlan.query.filter_by(project_id=self.id)
            .order_by(TestPlan.version.desc())
            .first()
        )

    @property
    def latest_run(self):
        from app.models.test_run import TestRun
        return (
            TestRun.query.filter_by(project_id=self.id)
            .order_by(TestRun.started_at.desc())
            .first()
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "target_url": self.target_url,
            "auth_type": self.auth_type,
            "credentials": self.get_masked_credentials(),
            "scope_instructions": self.scope_instructions,
            "prd_text": self.prd_text,
            "crawl_depth": self.crawl_depth or 2,
            "max_pages": self.max_pages or 10,
            "target_test_count": self.target_test_count or 12,
            "exploration_strategy": self.exploration_strategy or "balanced",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
