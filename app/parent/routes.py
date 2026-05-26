from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..auth.models import User, ParentStudentLink
from ..enrollments.models import Enrollment
from ..payments.models import Payment
from ..middleware.auth_guard import jwt_required_custom
from ..middleware.role_guard import role_required

parent_bp = Blueprint('parent', __name__)

@parent_bp.route('/link-student', methods=['POST'])
@jwt_required_custom
@role_required('parent')
def link_student():
    data = request.get_json() or {}
    student_code = data.get('student_code', '').strip()

    if not student_code:
        return jsonify({
            'success': False,
            'message': 'Student code is required',
            'error_code': 'VALIDATION_ERROR'
        }), 400

    student = User.query.filter_by(student_code=student_code, role='student').first()
    if not student:
        return jsonify({
            'success': False,
            'message': 'Invalid student code',
            'error_code': 'INVALID_CODE'
        }), 404

    # Check if already linked
    existing_link = ParentStudentLink.query.filter_by(parent_id=g.current_user.id, student_id=student.id).first()
    if existing_link:
        return jsonify({
            'success': False,
            'message': 'Student is already linked to your account',
            'error_code': 'ALREADY_LINKED'
        }), 400

    link = ParentStudentLink(parent_id=g.current_user.id, student_id=student.id)
    db.session.add(link)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Student linked successfully',
        'data': {
            'student_id': str(student.id),
            'name': student.name
        }
    }), 200


@parent_bp.route('/children', methods=['GET'])
@jwt_required_custom
@role_required('parent')
def get_children():
    links = ParentStudentLink.query.filter_by(parent_id=g.current_user.id).all()
    
    children_data = []
    for link in links:
        student = link.student
        children_data.append({
            'id': str(student.id),
            'name': student.name,
            'email': student.email,
            'student_code': student.student_code
        })

    return jsonify({
        'success': True,
        'data': children_data
    }), 200

def _verify_parent_student_link(student_id):
    """Helper to verify if a parent has access to a specific student."""
    return ParentStudentLink.query.filter_by(parent_id=g.current_user.id, student_id=student_id).first()

@parent_bp.route('/children/<student_id>/progress', methods=['GET'])
@jwt_required_custom
@role_required('parent')
def get_child_progress(student_id):
    if not _verify_parent_student_link(student_id):
        return jsonify({'success': False, 'message': 'Access denied or student not found'}), 403

    enrollments = Enrollment.query.filter_by(student_id=student_id).all()
    progress_data = []
    for e in enrollments:
        progress_data.append({
            'enrollment_id': str(e.id),
            'batch_id': str(e.batch_id) if e.batch_id else None,
            'batch_name': e.batch.name if getattr(e, 'batch', None) else 'Unknown',
            'course_title': e.batch.course.title if getattr(e, 'batch', None) and getattr(e.batch, 'course', None) else 'Unknown',
            'status': e.status,
            'enrolled_at': e.enrolled_at.isoformat() if e.enrolled_at else None
        })

    return jsonify({
        'success': True,
        'data': progress_data
    }), 200

@parent_bp.route('/children/<student_id>/fees', methods=['GET'])
@jwt_required_custom
@role_required('parent')
def get_child_fees(student_id):
    if not _verify_parent_student_link(student_id):
        return jsonify({'success': False, 'message': 'Access denied or student not found'}), 403

    payments = Payment.query.filter_by(student_id=student_id).order_by(Payment.created_at.desc()).all()
    fees_data = [p.to_dict(with_batch=True) for p in payments]

    return jsonify({
        'success': True,
        'data': fees_data
    }), 200

