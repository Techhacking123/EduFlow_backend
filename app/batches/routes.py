from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..middleware.auth_guard import jwt_required_custom
from ..middleware.role_guard import role_required
from .models import Batch
from .schema import batch_schema, batches_schema
from ..enrollments.models import Enrollment
from ..payments.models import Payment
from ..courses.models import LessonProgress

batches_bp = Blueprint('batches', __name__)


@batches_bp.route('', methods=['GET'])
@jwt_required_custom
@role_required('admin')
def get_batches():
    """GET /api/v1/batches - Get all batches (admin only)."""
    from ..courses.schema import batch_schema, batches_schema
    
    course_id = request.args.get('course_id')
    status = request.args.get('status')

    query = Batch.query

    if course_id:
        query = query.filter_by(course_id=course_id)

    if status:
        query = query.filter_by(status=status)

    batches = query.all()
    result = batches_schema.dump(batches)

    return jsonify({
        'success': True,
        'data': result,
    }), 200


@batches_bp.route('', methods=['POST'])
@jwt_required_custom
@role_required('admin')
def create_batch():
    """POST /api/v1/batches - Create a new batch (admin only)."""
    data = request.get_json() or {}

    course_id = data.get('course_id')
    faculty_id = data.get('faculty_id')
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    max_students = data.get('max_students', 50)
    price = data.get('price', 0.00)
    is_free = data.get('is_free', False)

    if not course_id or not faculty_id or not name or not start_date or not end_date:
        return jsonify({
            'success': False,
            'message': 'course_id, faculty_id, name, start_date, and end_date are required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    current_date = db.func.current_date()
    status = 'upcoming'

    batch = Batch(
        course_id=course_id,
        faculty_id=faculty_id,
        name=name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        max_students=max_students,
        price=price,
        is_free=is_free,
        status=status,
    )

    db.session.add(batch)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Batch created successfully',
        'data': batch_schema.dump(batch),
    }), 201


@batches_bp.route('/<batch_id>', methods=['GET'])
@jwt_required_custom
def get_batch_detail(batch_id):
    """GET /api/v1/batches/<batch_id> - Get batch details with enrolled students."""
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

    active_enrollments = [e for e in batch.enrollments if e.status != 'dropped']
    student_count = len(active_enrollments)
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(
        batch_id=batch_id,
        status='paid'
    ).scalar() or 0.00

    result = batch_schema.dump(batch)
    result['enrollment_count'] = student_count
    result['seats_available'] = batch.max_students - student_count
    result['total_revenue'] = float(total_revenue)

    return jsonify({
        'success': True,
        'data': result,
    }), 200


@batches_bp.route('/<batch_id>', methods=['PUT'])
@jwt_required_custom
def update_batch(batch_id):
    """PUT /api/v1/batches/<batch_id> - Update a batch."""
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
                'message': 'You do not have permission to update this batch',
                'error_code': 'FORBIDDEN',
            }), 403

    data = request.get_json() or {}

    if g.current_user.role == 'faculty':
        allowed_fields = ['price', 'is_free', 'description']
        for field in data:
            if field not in allowed_fields:
                return jsonify({
                    'success': False,
                    'message': f'Faculty can only update: {", ".join(allowed_fields)}',
                    'error_code': 'FORBIDDEN',
                }), 403

    if 'name' in data:
        batch.name = data['name'].strip()
    if 'description' in data:
        batch.description = data['description'].strip()
    if 'max_students' in data:
        batch.max_students = data['max_students']
    if 'price' in data:
        batch.price = data['price']
    if 'is_free' in data:
        batch.is_free = data['is_free']
        if batch.is_free:
            batch.price = 0.00

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Batch updated successfully',
        'data': batch_schema.dump(batch),
    }), 200


@batches_bp.route('/<batch_id>/price', methods=['PUT'])
@jwt_required_custom
def update_batch_price(batch_id):
    """PUT /api/v1/batches/<batch_id>/price - Update batch price and is_free flag (faculty only)."""
    batch = Batch.query.filter_by(id=batch_id).first()

    if not batch:
        return jsonify({
            'success': False,
            'message': 'Batch not found',
            'error_code': 'NOT_FOUND',
        }), 404

    if g.current_user.role != 'faculty':
        return jsonify({
            'success': False,
            'message': 'Only faculty can update batch pricing',
            'error_code': 'FORBIDDEN',
        }), 403

    if batch.faculty_id != g.current_user.id:
        return jsonify({
            'success': False,
            'message': 'You can only update pricing for batches assigned to you',
            'error_code': 'FORBIDDEN',
        }), 403

    data = request.get_json() or {}

    price = data.get('price')
    is_free = data.get('is_free')

    if price is not None:
        if price < 0:
            return jsonify({
                'success': False,
                'message': 'Price cannot be negative',
                'error_code': 'VALIDATION_ERROR',
            }), 422
        batch.price = price

    if is_free is not None:
        batch.is_free = is_free
        if batch.is_free:
            batch.price = 0.00

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Batch pricing updated successfully',
        'data': batch_schema.dump(batch),
    }), 200


@batches_bp.route('/my-batches', methods=['GET'])
@jwt_required_custom
@role_required('faculty')
def get_my_batches():
    """GET /api/v1/batches/my-batches - Get all batches assigned to current faculty."""
    batches = Batch.query.filter_by(faculty_id=g.current_user.id).all()

    result = []
    for batch in batches:
        batch_data = batch_schema.dump(batch)
        active_enrollments = [e for e in batch.enrollments if e.status != 'dropped']
        dropped_enrollments = [e for e in batch.enrollments if e.status == 'dropped']
        
        student_count = len(active_enrollments)
        dropped_count = len(dropped_enrollments)
        
        total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(
            batch_id=batch.id,
            status='paid'
        ).scalar() or 0.00

        batch_data['enrollment_count'] = student_count
        batch_data['dropped_count'] = dropped_count
        batch_data['seats_available'] = batch.max_students - student_count
        batch_data['total_revenue'] = float(total_revenue)
        
        from ..courses.schema import course_schema
        batch_data['course'] = course_schema.dump(batch.course) if batch.course else None
        
        result.append(batch_data)

    return jsonify({
        'success': True,
        'data': result,
    }), 200


@batches_bp.route('/<batch_id>/students', methods=['GET'])
@jwt_required_custom
def get_batch_students(batch_id):
    """GET /api/v1/batches/<batch_id>/students - Get enrolled students for a batch."""
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

    students = []
    for enrollment in batch.enrollments:
        student_data = {
            'id': enrollment.student_id,
            'name': enrollment.student.name,
            'email': enrollment.student.email,
            'status': enrollment.status,
            'is_paid': enrollment.is_paid,
            'enrolled_at': enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            'progress_percent': 0.0,
        }

        total_lessons = len(batch.course.lessons)
        if total_lessons > 0:
            completed_lessons = db.session.query(db.func.count(LessonProgress.id)).filter_by(
                student_id=enrollment.student_id,
                is_completed=True
            ).scalar() or 0
            student_data['progress_percent'] = round((completed_lessons / total_lessons) * 100, 2)

        students.append(student_data)

    return jsonify({
        'success': True,
        'data': {
            'batch_id': batch_id,
            'batch_name': batch.name,
            'students': students,
            'total_students': len(students),
        },
    }), 200

import datetime
import uuid

@batches_bp.route('/<batch_id>/attendance', methods=['GET'])
@jwt_required_custom
def get_batch_attendance(batch_id):
    """GET /api/v1/batches/<batch_id>/attendance - Get attendance for all students on a specific date (faculty)."""
    batch = Batch.query.filter_by(id=batch_id).first()
    if not batch:
        return jsonify({'success': False, 'message': 'Batch not found', 'error_code': 'NOT_FOUND'}), 404

    if g.current_user.role == 'faculty' and batch.faculty_id != g.current_user.id:
        return jsonify({'success': False, 'message': 'Forbidden', 'error_code': 'FORBIDDEN'}), 403

    date_str = request.args.get('date')
    if not date_str:
        target_date = datetime.date.today()
    else:
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format', 'error_code': 'VALIDATION_ERROR'}), 422

    from .models import AttendanceLog

    # If it's a Sunday, normally there's no class, but let's just return "rest_day" for everyone
    is_sunday = target_date.weekday() == 6

    # Fetch logs for this date
    logs = AttendanceLog.query.filter_by(batch_id=batch_id, date=target_date).all()
    log_map = {log.student_id: log for log in logs}

    students_attendance = []
    for enrollment in batch.enrollments:
        if enrollment.status == 'dropped':
            continue
        
        status = 'absent'
        if is_sunday:
            status = 'rest_day'
        
        if enrollment.student_id in log_map:
            status = log_map[enrollment.student_id].status

        students_attendance.append({
            'student_id': enrollment.student_id,
            'name': enrollment.student.name,
            'email': enrollment.student.email,
            'status': status
        })

    return jsonify({
        'success': True,
        'data': {
            'date': target_date.isoformat(),
            'is_sunday': is_sunday,
            'attendance': students_attendance
        }
    }), 200


@batches_bp.route('/<batch_id>/attendance/student/<student_id>', methods=['GET'])
@jwt_required_custom
def get_student_batch_attendance(batch_id, student_id):
    """GET /api/v1/batches/<batch_id>/attendance/student/<student_id> - Get attendance history for a student."""
    batch = Batch.query.filter_by(id=batch_id).first()
    if not batch:
        return jsonify({'success': False, 'message': 'Batch not found'}), 404

    # Parent/student auth check
    if g.current_user.role == 'student' and g.current_user.id != uuid.UUID(student_id):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    elif g.current_user.role == 'parent':
        from ..auth.models import ParentStudentLink
        link = ParentStudentLink.query.filter_by(parent_id=g.current_user.id, student_id=student_id).first()
        if not link:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403

    from .models import AttendanceLog
    from ..enrollments.models import Enrollment

    enrollment = Enrollment.query.filter_by(batch_id=batch_id, student_id=student_id).first()
    if not enrollment:
        return jsonify({'success': False, 'message': 'Student not enrolled in batch'}), 404

    start_date = enrollment.enrolled_at.date()
    end_date = datetime.date.today()

    logs = AttendanceLog.query.filter_by(batch_id=batch_id, student_id=student_id).all()
    log_map = {log.date: log for log in logs}

    history = []
    current_date = start_date
    present_count = 0
    total_days = 0

    while current_date <= end_date:
        is_sunday = current_date.weekday() == 6
        
        status = 'absent'
        if is_sunday:
            status = 'rest_day'
        
        if current_date in log_map:
            status = log_map[current_date].status
            
        if status != 'rest_day':
            total_days += 1
            if status == 'present':
                present_count += 1

        history.append({
            'date': current_date.isoformat(),
            'status': status
        })
        current_date += datetime.timedelta(days=1)

    # Sort descending
    history.reverse()
    
    percentage = round((present_count / total_days * 100) if total_days > 0 else 0, 2)

    return jsonify({
        'success': True,
        'data': {
            'student_id': student_id,
            'batch_id': batch_id,
            'percentage': percentage,
            'present_days': present_count,
            'total_working_days': total_days,
            'history': history
        }
    }), 200
