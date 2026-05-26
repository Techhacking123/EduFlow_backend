from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..middleware.auth_guard import jwt_required_custom
from ..middleware.role_guard import role_required
from ..batches.models import Batch
from ..payments.models import Payment
from ..courses.models import Course, Lesson
from ..courses.models import LessonProgress as LessonProgressModel
from .models import Enrollment
from .schema import enrollment_schema, enrollments_schema
from ..courses.schema import course_schema, batch_schema

enrollments_bp = Blueprint('enrollments', __name__)


@enrollments_bp.route('/free', methods=['POST'])
@jwt_required_custom
def enroll_free_batch():
    """POST /api/v1/enrollments/free - Enroll in a free batch."""
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

    if not batch.is_free:
        return jsonify({
            'success': False,
            'message': 'Batch is not free. Use /api/v1/payments/create-order instead.',
            'error_code': 'INVALID_REQUEST',
        }), 422

    if batch.enrollment_count >= batch.max_students:
        return jsonify({
            'success': False,
            'message': 'Batch is full',
            'error_code': 'BATCH_FULL',
        }), 422

    existing_enrollment = Enrollment.query.filter_by(
        student_id=g.current_user.id,
        batch_id=batch_id
    ).first()

    if existing_enrollment:
        if existing_enrollment.status != 'dropped':
            return jsonify({
                'success': False,
                'message': 'Already enrolled in this batch',
                'error_code': 'ALREADY_ENROLLED',
            }), 409
        # Re-enroll a dropped student
        existing_enrollment.status = 'active'
        existing_enrollment.is_paid = True
        existing_enrollment.approved_at = db.func.now()
        enrollment_id = existing_enrollment.id
    else:
        enrollment = Enrollment(
            student_id=g.current_user.id,
            batch_id=batch_id,
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
        'message': 'Enrolled successfully',
        'data': {
            'enrollment_id': str(enrollment_id),
        },
    }), 200


@enrollments_bp.route('/my-enrollments', methods=['GET'])
@jwt_required_custom
def get_my_enrollments():
    """GET /api/v1/enrollments/my-enrollments - Get all enrollments for current student."""
    enrollments = Enrollment.query.filter(
        Enrollment.student_id == g.current_user.id,
        Enrollment.status != 'dropped'
    ).all()

    result = []
    for enrollment in enrollments:
        enrollment_data = enrollment_schema.dump(enrollment)
        
        if enrollment.batch:
            batch_data = batch_schema.dump(enrollment.batch)
            batch_data['course'] = course_schema.dump(enrollment.batch.course) if enrollment.batch.course else None
            
            total_lessons = len(enrollment.batch.course.lessons) if enrollment.batch.course else 0
            completed_lessons = LessonProgressModel.query.join(Lesson).filter(
                LessonProgressModel.student_id == g.current_user.id,
                LessonProgressModel.is_completed == True,
                Lesson.course_id == enrollment.batch.course.id
            ).count() if enrollment.batch.course else 0
            progress_percent = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
            
            enrollment_data['progress_percent'] = round(progress_percent, 2)
            enrollment_data['total_lessons'] = total_lessons
            enrollment_data['completed_lessons'] = completed_lessons
            enrollment_data['batch'] = batch_data
        
        result.append(enrollment_data)

    return jsonify({
        'success': True,
        'data': result,
    }), 200


@enrollments_bp.route('', methods=['GET'])
@jwt_required_custom
@role_required('admin')
def get_all_enrollments():
    """GET /api/v1/enrollments - Get all enrollments (admin only)."""
    status = request.args.get('status')
    
    query = Enrollment.query
    if status:
        query = query.filter_by(status=status)
        
    enrollments = query.order_by(Enrollment.enrolled_at.desc()).all()
    
    result = []
    for enrollment in enrollments:
        data = enrollment_schema.dump(enrollment)
        
        # Include student info
        if enrollment.student:
            data['student'] = {
                'id': str(enrollment.student.id),
                'name': enrollment.student.name,
                'email': enrollment.student.email
            }
            
        # Include batch & course info
        if enrollment.batch:
            batch_data = batch_schema.dump(enrollment.batch)
            batch_data['course'] = course_schema.dump(enrollment.batch.course) if enrollment.batch.course else None
            data['batch'] = batch_data
            
        result.append(data)
        
    return jsonify({
        'success': True,
        'data': result
    }), 200




@enrollments_bp.route('/<enrollment_id>/approve', methods=['PUT'])
@jwt_required_custom
@role_required('admin')
def approve_enrollment(enrollment_id):
    """PUT /api/v1/enrollments/<enrollment_id>/approve - Approve enrollment (admin only)."""
    enrollment = Enrollment.query.filter_by(id=enrollment_id).first()

    if not enrollment:
        return jsonify({
            'success': False,
            'message': 'Enrollment not found',
            'error_code': 'NOT_FOUND',
        }), 404

    enrollment.status = 'active'
    enrollment.approved_at = db.func.now()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Enrollment approved successfully',
        'data': enrollment_schema.dump(enrollment),
    }), 200


@enrollments_bp.route('/<enrollment_id>/drop', methods=['PUT'])
@jwt_required_custom
def drop_enrollment(enrollment_id):
    """PUT /api/v1/enrollments/<enrollment_id>/drop - Drop/enrollment (student or admin)."""
    enrollment = Enrollment.query.filter_by(id=enrollment_id).first()

    if not enrollment:
        return jsonify({
            'success': False,
            'message': 'Enrollment not found',
            'error_code': 'NOT_FOUND',
        }), 404

    if g.current_user.role != 'admin':
        if enrollment.student_id != g.current_user.id:
            return jsonify({
                'success': False,
                'message': 'You can only drop your own enrollment',
                'error_code': 'FORBIDDEN',
            }), 403

    enrollment.status = 'dropped'
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Enrollment dropped successfully',
        'data': enrollment_schema.dump(enrollment),
    }), 200
