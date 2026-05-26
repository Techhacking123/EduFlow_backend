import datetime

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
