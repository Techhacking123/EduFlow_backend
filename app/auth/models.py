import uuid
from datetime import datetime
from ..extensions import db, bcrypt


import string
import random

def generate_student_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

class ParentStudentLink(db.Model):
    """Model to link parents to their children (students)."""
    __tablename__ = 'parent_student_links'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    parent_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    student_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Establish relationships to the users table
    parent = db.relationship('User', foreign_keys=[parent_id], backref=db.backref('linked_students', cascade='all, delete-orphan'))
    student = db.relationship('User', foreign_keys=[student_id], backref=db.backref('linked_parents', cascade='all, delete-orphan'))
    
    __table_args__ = (
        db.UniqueConstraint('parent_id', 'student_id', name='uq_parent_student'),
    )

class User(db.Model):
    """User model for authentication and profile."""
    __tablename__ = 'users'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    institute_id = db.Column(db.UUID(as_uuid=True), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_email_verified = db.Column(db.Boolean, default=False)
    student_code = db.Column(db.String(10), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    refresh_tokens = db.relationship(
        'RefreshToken',
        backref='user',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    VALID_ROLES = ('student', 'faculty', 'admin', 'parent')

    def set_password(self, password):
        """Hash and set the user password."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Verify password against the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Serialize user to dictionary."""
        return {
            'id': str(self.id) if self.id else None,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'phone': self.phone,
            'student_code': self.student_code,
            'is_active': self.is_active,
            'is_email_verified': self.is_email_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<User {self.email}>'


class RefreshToken(db.Model):
    """Model to store refresh tokens for JWT auth."""
    __tablename__ = 'refresh_tokens'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    token = db.Column(db.Text, nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_expired(self):
        """Check if the refresh token has expired."""
        return datetime.utcnow() > self.expires_at

    def __repr__(self):
        return f'<RefreshToken user_id={self.user_id}>'
