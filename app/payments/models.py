import uuid
from datetime import datetime
from ..extensions import db


class Payment(db.Model):
    """Payment record for batch enrollment."""
    __tablename__ = 'payments'

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
    student = db.relationship(
        'User',
        foreign_keys=[student_id],
        lazy=True,
    )
    batch = db.relationship(
        'Batch',
        backref='payments_ref',
        lazy=True,
    )
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(10), default='INR')
    status = db.Column(db.String(20), default='pending')
    razorpay_order_id = db.Column(db.String(100), unique=True)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)
    razorpay_signature = db.Column(db.String(300), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    VALID_STATUSES = ('pending', 'paid', 'failed', 'refunded')

    enrollment = db.relationship(
        'Enrollment',
        backref='payment',
        uselist=False,
        cascade='all, delete-orphan',
    )

    def to_dict(self, with_enrollment=False, with_batch=False):
        """Serialize payment to dictionary."""
        data = {
            'id': str(self.id),
            'student_id': str(self.student_id),
            'batch_id': str(self.batch_id),
            'amount': float(self.amount) if self.amount else 0.0,
            'currency': self.currency,
            'status': self.status,
            'razorpay_order_id': self.razorpay_order_id,
            'razorpay_payment_id': self.razorpay_payment_id,
            'razorpay_signature': self.razorpay_signature,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        if with_enrollment:
            data['enrollment'] = self.enrollment.to_dict() if self.enrollment else None

        if with_batch:
            data['batch'] = self.batch.to_dict() if self.batch else None

        return data

    def __repr__(self):
        return f'<Payment {self.id} student_id={self.student_id}>'
