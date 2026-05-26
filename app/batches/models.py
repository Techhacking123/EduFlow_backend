import uuid
from datetime import datetime, date
from ..extensions import db


class Batch(db.Model):
    """Batch model - grouping of students for a course with specific faculty and pricing."""
    __tablename__ = 'batches'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('courses.id'),
        nullable=False,
    )
    faculty_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('users.id'),
        nullable=False,
    )
    faculty = db.relationship(
        'User',
        foreign_keys=[faculty_id],
        lazy=True,
    )
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    max_students = db.Column(db.Integer, default=50)
    price = db.Column(db.Numeric(10, 2), default=0.00)
    is_free = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='upcoming')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    enrollments = db.relationship(
        'Enrollment',
        backref='batch',
        lazy=True,
        cascade='all, delete-orphan',
    )
    
    attendance_logs = db.relationship(
        'AttendanceLog',
        backref='batch',
        lazy=True,
        cascade='all, delete-orphan',
    )

    VALID_STATUSES = ('upcoming', 'ongoing', 'completed')

    def to_dict(self, with_enrollment_count=False):
        """Serialize batch to dictionary."""
        data = {
            'id': str(self.id),
            'course_id': str(self.course_id),
            'faculty_id': str(self.faculty_id),
            'name': self.name,
            'description': self.description,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'max_students': self.max_students,
            'price': float(self.price) if self.price else 0.0,
            'is_free': self.is_free,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        if with_enrollment_count:
            data['enrollment_count'] = len(self.enrollments)
            data['seats_available'] = self.max_students - len(self.enrollments)

        return data

    def __repr__(self):
        return f'<Batch {self.name}>'


class AttendanceLog(db.Model):
    """Tracks daily automated attendance based on activity."""
    __tablename__ = 'attendance_logs'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    batch_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('batches.id'),
        nullable=False,
    )
    student_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('users.id'),
        nullable=False,
    )
    date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(20), default='present')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint('batch_id', 'student_id', 'date', name='uq_attendance_batch_student_date'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'batch_id': str(self.batch_id),
            'student_id': str(self.student_id),
            'date': self.date.isoformat() if self.date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<AttendanceLog {self.student_id} {self.date} {self.status}>'

