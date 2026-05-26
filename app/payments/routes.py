import hmac
import hashlib
from flask import Blueprint, request, jsonify, g, current_app
from ..extensions import db
from ..middleware.auth_guard import jwt_required_custom
from ..middleware.role_guard import role_required
from ..courses.models import Course, Lesson
from ..batches.models import Batch
from ..enrollments.models import Enrollment
from .models import Payment
from .schema import payment_schema, payments_schema
from ..auth.models import User

payments_bp = Blueprint('payments', __name__)


def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """Verify Razorpay payment signature using HMAC."""
    from flask import current_app
    razorpay_key_secret = current_app.config.get('RAZORPAY_KEY_SECRET', '')
    generated_signature = hmac.new(
        key=razorpay_key_secret.encode(),
        msg=f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(generated_signature, razorpay_signature)


def get_razorpay_client():
    """Get Razorpay client instance."""
    from flask import current_app
    razorpay_key_id = current_app.config.get('RAZORPAY_KEY_ID', '')
    razorpay_key_secret = current_app.config.get('RAZORPAY_KEY_SECRET', '')
    import razorpay
    return razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))


@payments_bp.route('/create-order', methods=['POST'])
@jwt_required_custom
def create_payment_order():
    """POST /api/v1/payments/create-order - Create a Razorpay payment order."""
    data = request.get_json() or {}

    batch_id = data.get('batch_id')

    if not batch_id:
        return jsonify({
            'success': False,
            'message': 'batch_id is required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    batch = Batch.query.filter_by(id=batch_id).first()

    if not batch:
        return jsonify({
            'success': False,
            'message': 'Batch not found',
            'error_code': 'NOT_FOUND',
        }), 404

    if not batch.course.is_published:
        return jsonify({
            'success': False,
            'message': 'Course is not published',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    if batch.is_free:
        return jsonify({
            'success': False,
            'message': 'Batch is free. Use /api/v1/enrollments/free instead.',
            'error_code': 'INVALID_REQUEST',
        }), 422

    if len(batch.enrollments) >= batch.max_students:
        return jsonify({
            'success': False,
            'message': 'Batch is full',
            'error_code': 'BATCH_FULL',
        }), 422

    existing_enrollment = Enrollment.query.filter_by(
        student_id=g.current_user.id,
        batch_id=batch_id
    ).first()

    if existing_enrollment and existing_enrollment.status != 'dropped':
        return jsonify({
            'success': False,
            'message': 'Already enrolled in this batch',
            'error_code': 'ALREADY_ENROLLED',
        }), 409

    payment = Payment(
        student_id=g.current_user.id,
        batch_id=batch_id,
        amount=batch.price,
        currency='INR',
        status='pending',
    )
    db.session.add(payment)
    db.session.commit()

    amount_paise = int(batch.price * 100)

    try:
        order = get_razorpay_client().order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': str(payment.id),
            'payment_capture': 1
        })
    except Exception as e:
        payment.status = 'failed'
        db.session.commit()
        return jsonify({
            'success': False,
            'message': f'Failed to create Razorpay order. Please check Razorpay credentials. Error: {str(e)}',
            'error_code': 'PAYMENT_GATEWAY_ERROR',
        }), 502

    payment.razorpay_order_id = order['id']
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Payment order created',
        'data': {
            'order_id': order['id'],
            'amount': amount_paise,
            'currency': 'INR',
            'key_id': current_app.config.get('RAZORPAY_KEY_ID', ''),
            'payment_db_id': str(payment.id),
            'student_name': g.current_user.name,
            'student_email': g.current_user.email,
        },
    }), 200


@payments_bp.route('/verify', methods=['POST'])
@jwt_required_custom
def verify_payment():
    """POST /api/v1/payments/verify - Verify Razorpay payment and create enrollment."""
    data = request.get_json() or {}

    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')
    payment_db_id = data.get('payment_db_id')
    batch_id = data.get('batch_id')

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, payment_db_id, batch_id]):
        return jsonify({
            'success': False,
            'message': 'All fields are required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    payment = Payment.query.filter_by(id=payment_db_id).first()

    if not payment:
        return jsonify({
            'success': False,
            'message': 'Payment record not found',
            'error_code': 'NOT_FOUND',
        }), 404

    if not verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        return jsonify({
            'success': False,
            'message': 'Payment verification failed',
            'error_code': 'SIGNATURE_MISMATCH',
        }), 400

    payment.status = 'paid'
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.paid_at = db.func.now()
    db.session.commit()

    existing_enrollment = Enrollment.query.filter_by(
        student_id=g.current_user.id,
        batch_id=batch_id
    ).first()

    if existing_enrollment:
        existing_enrollment.payment_id = payment.id
        existing_enrollment.status = 'active'
        existing_enrollment.is_paid = True
        existing_enrollment.approved_at = db.func.now()
        enrollment_id = existing_enrollment.id
    else:
        enrollment = Enrollment(
            student_id=g.current_user.id,
            batch_id=batch_id,
            payment_id=payment.id,
            status='active',
            is_paid=True,
            approved_at=db.func.now(),
        )
        db.session.add(enrollment)
        db.session.flush()
        enrollment_id = enrollment.id
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Payment successful',
        'data': {
            'enrollment_id': str(enrollment_id),
            'payment_id': payment.id,
        },
    }), 200


@payments_bp.route('/my-history', methods=['GET'])
@jwt_required_custom
def get_my_payment_history():
    """GET /api/v1/payments/my-history - Get payment history for current student."""
    payments = Payment.query.filter_by(student_id=g.current_user.id).all()

    result = []
    for payment in payments:
        payment_data = payment_schema.dump(payment)
        payment_data['batch_name'] = payment.batch.name if payment.batch else None
        payment_data['course_title'] = payment.batch.course.title if payment.batch and payment.batch.course else None
        payment_data['faculty_name'] = payment.batch.faculty.name if payment.batch and payment.batch.faculty else None
        result.append(payment_data)

    return jsonify({
        'success': True,
        'data': result,
    }), 200


@payments_bp.route('/batch/<batch_id>/revenue', methods=['GET'])
@jwt_required_custom
def get_batch_revenue(batch_id):
    """GET /api/v1/payments/batch/<batch_id>/revenue - Get revenue for a batch."""
    batch = Batch.query.filter_by(id=batch_id).first()

    if not batch:
        return jsonify({
            'success': False,
            'message': 'Batch not found',
            'error_code': 'NOT_FOUND',
        }), 404

    if g.current_user.role == 'faculty':
        if batch.faculty_id != g.current_user.id:
            return jsonify({
                'success': False,
                'message': 'You do not have permission to view this batch',
                'error_code': 'FORBIDDEN',
            }), 403

    total_paid_enrollments = Enrollment.query.filter_by(
        batch_id=batch_id,
        is_paid=True,
        status='active'
    ).count()

    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(
        batch_id=batch_id,
        status='paid'
    ).scalar() or 0.00

    payments = Payment.query.filter_by(
        batch_id=batch_id,
        status='paid'
    ).all()

    payment_list = [payment_schema.dump(p) for p in payments]

    return jsonify({
        'success': True,
        'data': {
            'batch_id': batch_id,
            'batch_name': batch.name,
            'total_paid_enrollments': total_paid_enrollments,
            'total_revenue': float(total_revenue),
            'payments': payment_list,
        },
    }), 200


@payments_bp.route('/revenue/summary', methods=['GET'])
@jwt_required_custom
@role_required('admin')
def get_revenue_summary():
    """GET /api/v1/payments/revenue/summary - Get overall revenue summary (admin only)."""
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(
        status='paid'
    ).scalar() or 0.00

    total_enrollments = db.session.query(db.func.count(Enrollment.id)).filter_by(
        status='active',
        is_paid=True
    ).count()

    course_breakdown = db.session.query(
        Course.id,
        Course.title,
        db.func.sum(Payment.amount).label('total_revenue'),
        db.func.count(Enrollment.id).label('total_enrollments')
    ).join(
        Batch, Course.id == Batch.course_id
    ).join(
        Enrollment, Batch.id == Enrollment.batch_id
    ).join(
        Payment, Enrollment.payment_id == Payment.id
    ).filter(
        Payment.status == 'paid'
    ).group_by(Course.id, Course.title).all()

    faculty_breakdown = db.session.query(
        User.id.label('faculty_id'),
        User.name.label('faculty_name'),
        db.func.sum(Payment.amount).label('total_revenue'),
        db.func.count(Enrollment.id).label('total_enrollments')
    ).join(
        Batch, User.id == Batch.faculty_id
    ).join(
        Enrollment, Batch.id == Enrollment.batch_id
    ).join(
        Payment, Enrollment.payment_id == Payment.id
    ).filter(
        Payment.status == 'paid'
    ).group_by(User.id, User.name).all()

    course_list = [
        {
            'course_id': c[0],
            'course_title': c[1],
            'total_revenue': float(c[2]) if c[2] else 0.0,
            'total_enrollments': c[3],
        }
        for c in course_breakdown
    ]

    faculty_list = [
        {
            'faculty_id': f[0],
            'faculty_name': f[1],
            'total_revenue': float(f[2]) if f[2] else 0.0,
            'total_enrollments': f[3],
        }
        for f in faculty_breakdown
    ]

    return jsonify({
        'success': True,
        'data': {
            'total_revenue': float(total_revenue),
            'total_enrollments': total_enrollments,
            'course_breakdown': course_list,
            'faculty_breakdown': faculty_list,
        },
    }), 200