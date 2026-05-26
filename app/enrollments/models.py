import uuid
from datetime import datetime
from ..extensions import db


class Enrollment(db.Model):
    """Student enrollment record for a batch."""
    __tablename__ = 'enrollments'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    student_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('users.id'),
        nullable=False,
    )
    batch_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('batches.id'),
        nullable=False,
    )
    payment_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('payments.id'),
        nullable=True,
    )
    student = db.relationship(
        'User',
        foreign_keys=[student_id],
        lazy=True,
    )
    status = db.Column(db.String(20), default='pending')
    is_paid = db.Column(db.Boolean, default=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'batch_id'),
    )

    VALID_STATUSES = ('pending', 'active', 'completed', 'dropped')

    def to_dict(self, with_student=False, with_batch=False, with_course=False):
        """Serialize enrollment to dictionary."""
        data = {
            'id': str(self.id),
            'student_id': str(self.student_id),
            'batch_id': str(self.batch_id),
            'payment_id': str(self.payment_id) if self.payment_id else None,
            'status': self.status,
            'is_paid': self.is_paid,
            'enrolled_at': self.enrolled_at.isoformat() if self.enrolled_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
        }

        if with_batch and getattr(self, 'batch', None):
            data['batch'] = self.batch.to_dict()

        if with_course and getattr(self, 'batch', None) and getattr(self.batch, 'course', None):
            data['course'] = self.batch.course.to_dict()

        return data

    def __repr__(self):
        return f'<Enrollment student_id={self.student_id} batch_id={self.batch_id}>'
