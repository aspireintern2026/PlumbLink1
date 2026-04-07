# app/models.py

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20), nullable=False
    )  # admin, customer, plumber
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            ),
        }


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    issue = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    urgency = db.Column(db.String(20), nullable=False)
    preferred_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "issue": self.issue,
            "description": self.description,
            "urgency": self.urgency,
            "preferred_time": self.preferred_time.isoformat()
            if self.preferred_time
            else None,
            "status": self.status,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
        }
