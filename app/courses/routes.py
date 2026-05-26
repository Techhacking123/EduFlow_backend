from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..middleware.auth_guard import jwt_required_custom, jwt_optional_custom
from ..middleware.role_guard import role_required
from .models import Course, Lesson, LessonProgress
from .schema import course_schema, courses_schema, lesson_schema, lessons_schema, lesson_progress_schema
from ..batches.models import Batch

courses_bp = Blueprint('courses', __name__)


@courses_bp.route('', methods=['GET'])
@jwt_optional_custom
def get_courses():
    category = request.args.get('category')
    search = request.args.get('search')

    query = Course.query
    # Visibility logic
    if not g.current_user:
        query = query.filter_by(is_published=True)
    elif g.current_user.role in ('student', 'parent'):
        query = query.filter_by(is_published=True)
    elif g.current_user.role == 'faculty':
        query = query.filter(
            db.or_(
                Course.is_published == True,
                Course.created_by == g.current_user.id
            )
        )
    # admins see all courses

    if category:
        query = query.filter_by(category=category)

    if search:
        query = query.filter(
            db.or_(
                Course.title.ilike(f'%{search}%'),
                Course.description.ilike(f'%{search}%'),
            )
        )

    courses = query.all()
    result = courses_schema.dump(courses)

    return jsonify({
        'success': True,
        'data': result,
    }), 200


@courses_bp.route('', methods=['POST'])
@jwt_required_custom
@role_required('admin', 'faculty')
def create_course():
    data = request.get_json() or {}

    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', '').strip()
    thumbnail_url = data.get('thumbnail_url', '').strip()

    if not title:
        return jsonify({
            'success': False,
            'message': 'Title is required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    course = Course(
        created_by=g.current_user.id,
        title=title,
        description=description,
        category=category,
        thumbnail_url=thumbnail_url,
        is_published=False,
    )

    db.session.add(course)
    db.session.commit()

    # Implicitly create a Batch if price is provided
    if 'price' in data:
        from datetime import datetime, timedelta
        price_val = float(data['price'])
        batch = Batch(
            course_id=course.id,
            faculty_id=g.current_user.id,
            name="Default Batch",
            description="Default batch for this course.",
            start_date=datetime.utcnow().date(),
            end_date=(datetime.utcnow() + timedelta(days=365)).date(),
            max_students=1000,
            price=price_val,
            is_free=(price_val == 0.0),
            status='ongoing'
        )
        db.session.add(batch)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Course created successfully',
        'data': course_schema.dump(course),
    }), 201


@courses_bp.route('/<course_id>/publish', methods=['POST'])
@jwt_required_custom
@role_required('admin', 'faculty')
def toggle_publish_course(course_id):
    """POST /api/v1/courses/<course_id>/publish - Toggle publish status."""
    course = Course.query.filter_by(id=course_id).first()

    if not course:
        return jsonify({
            'success': False,
            'message': 'Course not found',
            'error_code': 'NOT_FOUND',
        }), 404

    if g.current_user.role == 'faculty' and course.created_by != g.current_user.id:
        return jsonify({
            'success': False,
            'message': 'You do not have permission to publish this course',
            'error_code': 'FORBIDDEN',
        }), 403

    if not course.is_published:
        lesson_count = len(course.lessons)
        if lesson_count == 0:
            return jsonify({
                'success': False,
                'message': 'Cannot publish course with 0 lessons',
                'error_code': 'VALIDATION_ERROR',
            }), 422

    course.is_published = not course.is_published
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Course {"published" if course.is_published else "unpublished"} successfully',
        'data': course_schema.dump(course),
    }), 200



@courses_bp.route('/<course_id>', methods=['GET'])
@jwt_optional_custom
def get_course_detail(course_id):
    course = Course.query.filter_by(id=course_id).first()

    if not course:
        return jsonify({
            'success': False,
            'message': 'Course not found',
            'error_code': 'NOT_FOUND',
        }), 404

    result = course_schema.dump(course)

    result['lessons'] = []
    result['batches'] = []

    if g.current_user:
        student_id = g.current_user.id
    else:
        student_id = None

    for lesson in course.lessons:
        lesson_data = lesson.to_dict(with_progress=True, student_id=student_id)
        result['lessons'].append(lesson_data)

    from ..enrollments.models import Enrollment

    for batch in course.batches:
        batch_data = batch.to_dict()
        
        # Check if the current student is enrolled in this batch
        batch_data['is_enrolled'] = False
        if student_id:
            enrollment = Enrollment.query.filter_by(
                student_id=student_id, 
                batch_id=batch.id
            ).filter(Enrollment.status != 'dropped').first()
            if enrollment:
                batch_data['is_enrolled'] = True
                batch_data['enrollment_status'] = enrollment.status
                
        result['batches'].append(batch_data)

    return jsonify({
        'success': True,
        'data': result,
    }), 200


@courses_bp.route('/<course_id>', methods=['PUT'])
@jwt_required_custom
def update_course(course_id):
    course = Course.query.filter_by(id=course_id).first()

    if not course:
        return jsonify({
            'success': False,
            'message': 'Course not found',
            'error_code': 'NOT_FOUND',
        }), 404

    data = request.get_json() or {}

    if g.current_user.role == 'faculty':
        assigned_batch = False
        for batch in course.batches:
            if batch.faculty_id == g.current_user.id:
                assigned_batch = True
                break

        if not assigned_batch:
            return jsonify({
                'success': False,
                'message': 'You do not have permission to update this course',
                'error_code': 'FORBIDDEN',
            }), 403

    if 'title' in data:
        course.title = data['title'].strip()
    if 'description' in data:
        course.description = data['description'].strip()
    if 'category' in data:
        course.category = data['category'].strip()
    if 'thumbnail_url' in data:
        course.thumbnail_url = data['thumbnail_url'].strip()

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Course updated successfully',
        'data': course_schema.dump(course),
    }), 200




@courses_bp.route('/<course_id>/lessons', methods=['POST'])
@jwt_required_custom
@role_required('faculty')
def create_lesson(course_id):
    course = Course.query.filter_by(id=course_id).first()

    if not course:
        return jsonify({
            'success': False,
            'message': 'Course not found',
            'error_code': 'NOT_FOUND',
        }), 404

    data = request.get_json() or {}

    title = data.get('title', '').strip()
    lesson_type = data.get('type', '').strip()
    content_url = data.get('content_url')
    content_url = content_url.strip() if content_url else ''
    content_text = data.get('content_text')
    content_text = content_text.strip() if content_text else ''
    position = data.get('position', len(course.lessons) + 1)
    duration_mins = data.get('duration_mins')
    is_preview = data.get('is_preview', False)
    quiz_options = data.get('quiz_options') if lesson_type == 'assignment' else None
    quiz_correct_answer = data.get('quiz_correct_answer') if lesson_type == 'assignment' else None

    if not title:
        return jsonify({
            'success': False,
            'message': 'Title is required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    if lesson_type not in Lesson.VALID_TYPES:
        return jsonify({
            'success': False,
            'message': f'Invalid lesson type. Must be one of: {", ".join(Lesson.VALID_TYPES)}',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    if lesson_type in ('video', 'document') and not content_url:
        return jsonify({
            'success': False,
            'message': f'content_url is required for {lesson_type} lessons',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    from datetime import datetime, timezone
    live_start_time = None
    live_start_time_raw = data.get('live_start_time')
    if live_start_time_raw and lesson_type == 'live_class':
        try:
            iso_str = live_start_time_raw.replace('Z', '+00:00')
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            live_start_time = dt
        except Exception as e:
            print("Error parsing live_start_time:", e)

    lesson = Lesson(
        course_id=course_id,
        title=title,
        type=lesson_type,
        content_url=content_url if lesson_type in ('video', 'document', 'live_class') else None,
        content_text=content_text if lesson_type in ('text', 'assignment') else None,
        position=position,
        duration_mins=duration_mins,
        is_preview=is_preview,
        quiz_options=quiz_options,
        quiz_correct_answer=quiz_correct_answer,
        live_start_time=live_start_time,
    )

    db.session.add(lesson)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Lesson created successfully',
        'data': lesson_schema.dump(lesson),
    }), 201


@courses_bp.route('/<course_id>/lessons/<lesson_id>', methods=['PUT'])
@jwt_required_custom
@role_required('faculty')
def update_lesson(course_id, lesson_id):
    course = Course.query.filter_by(id=course_id).first()

    if not course:
        return jsonify({
            'success': False,
            'message': 'Course not found',
            'error_code': 'NOT_FOUND',
        }), 404

    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first()

    if not lesson:
        return jsonify({
            'success': False,
            'message': 'Lesson not found',
            'error_code': 'NOT_FOUND',
        }), 404

    data = request.get_json() or {}

    if 'title' in data:
        lesson.title = data['title'].strip()
    if 'content_url' in data:
        content_url = data['content_url']
        lesson.content_url = content_url.strip() if content_url else None
    if 'content_text' in data:
        content_text = data['content_text']
        lesson.content_text = content_text.strip() if content_text else None
    if 'duration_mins' in data:
        lesson.duration_mins = data['duration_mins']
    if 'is_preview' in data:
        lesson.is_preview = data['is_preview']
    if lesson.type == 'assignment':
        if 'quiz_options' in data:
            lesson.quiz_options = data['quiz_options']
        if 'quiz_correct_answer' in data:
            lesson.quiz_correct_answer = data['quiz_correct_answer']

    if 'live_start_time' in data:
        live_start_time_raw = data['live_start_time']
        if live_start_time_raw and lesson.type == 'live_class':
            try:
                from datetime import datetime, timezone
                iso_str = live_start_time_raw.replace('Z', '+00:00')
                dt = datetime.fromisoformat(iso_str)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                lesson.live_start_time = dt
            except Exception as e:
                print("Error parsing live_start_time in update:", e)
        else:
            lesson.live_start_time = None

    if 'position' in data:
        new_position = data['position']
        if new_position != lesson.position:
            if new_position < lesson.position:
                Lesson.query.filter(
                    Lesson.course_id == course_id,
                    Lesson.position >= new_position,
                    Lesson.position < lesson.position,
                ).update({Lesson.position:Lesson.position + 1})
            else:
                Lesson.query.filter(
                    Lesson.course_id == course_id,
                    Lesson.position > lesson.position,
                    Lesson.position <= new_position,
                ).update({Lesson.position:Lesson.position - 1})
            lesson.position = new_position

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Lesson updated successfully',
        'data': lesson_schema.dump(lesson),
    }), 200


@courses_bp.route('/<course_id>/lessons/<lesson_id>', methods=['DELETE'])
@jwt_required_custom
def delete_lesson(course_id, lesson_id):
    course = Course.query.filter_by(id=course_id).first()

    if not course:
        return jsonify({
            'success': False,
            'message': 'Course not found',
            'error_code': 'NOT_FOUND',
        }), 404

    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first()

    if not lesson:
        return jsonify({
            'success': False,
            'message': 'Lesson not found',
            'error_code': 'NOT_FOUND',
        }), 404

    if g.current_user.role == 'faculty':
        assigned_batch = False
        for batch in course.batches:
            if batch.faculty_id == g.current_user.id:
                assigned_batch = True
                break

        if not assigned_batch:
            return jsonify({
                'success': False,
                'message': 'You do not have permission to delete this lesson',
                'error_code': 'FORBIDDEN',
            }), 403

    db.session.delete(lesson)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Lesson deleted successfully',
    }), 200


@courses_bp.route('/<course_id>/lessons/<lesson_id>/progress', methods=['POST'])
@jwt_required_custom
def mark_lesson_complete(course_id, lesson_id):
    course = Course.query.filter_by(id=course_id).first()

    if not course:
        return jsonify({
            'success': False,
            'message': 'Course not found',
            'error_code': 'NOT_FOUND',
        }), 404

    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first()

    if not lesson:
        return jsonify({
            'success': False,
            'message': 'Lesson not found',
            'error_code': 'NOT_FOUND',
        }), 404

    progress = LessonProgress.query.filter_by(
        student_id=g.current_user.id,
        lesson_id=lesson_id
    ).first()
    
    selected_option = request.get_json().get('quiz_selected_option') if request.is_json else None

    if not progress:
        progress = LessonProgress(
            student_id=g.current_user.id,
            lesson_id=lesson_id,
            is_completed=True,
            completed_at=db.func.now(),
            quiz_selected_option=selected_option
        )
        db.session.add(progress)
    else:
        progress.is_completed = True
        progress.completed_at = db.func.now()
        if selected_option:
            progress.quiz_selected_option = selected_option

    db.session.commit()

    # --- Automated Attendance Logic ---
    from datetime import date
    from ..batches.models import Batch, AttendanceLog
    from ..enrollments.models import Enrollment

    # Find the student's active enrollment for this course's batches
    enrollment = Enrollment.query.join(Batch).filter(
        Enrollment.student_id == g.current_user.id,
        Batch.course_id == course_id,
        Enrollment.status != 'dropped'
    ).first()

    if enrollment:
        today = date.today()
        existing_log = AttendanceLog.query.filter_by(
            batch_id=enrollment.batch_id,
            student_id=g.current_user.id,
            date=today
        ).first()

        if not existing_log:
            new_log = AttendanceLog(
                batch_id=enrollment.batch_id,
                student_id=g.current_user.id,
                date=today,
                status='present'
            )
            db.session.add(new_log)
            db.session.commit()
    # ----------------------------------

    total_lessons = len(course.lessons)
    completed_lessons = LessonProgress.query.filter_by(
        student_id=g.current_user.id,
        is_completed=True
    ).count()

    completion_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0

    return jsonify({
        'success': True,
        'message': 'Lesson marked as complete',
        'data': {
            'lesson_id': lesson_id,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'completion_percentage': round(completion_percentage, 2),
        },
    }), 200


@courses_bp.route('/<course_id>/my-progress', methods=['GET'])
@jwt_required_custom
def get_my_progress(course_id):
    course = Course.query.filter_by(id=course_id).first()

    if not course:
        return jsonify({
            'success': False,
            'message': 'Course not found',
            'error_code': 'NOT_FOUND',
        }), 404

    total_lessons = len(course.lessons)
    completed_lessons = LessonProgress.query.join(Lesson).filter(
        LessonProgress.student_id == g.current_user.id,
        LessonProgress.is_completed == True,
        Lesson.course_id == course_id
    ).count()

    completion_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0

    lessons = []
    for lesson in course.lessons:
        progress = LessonProgress.query.filter_by(
            student_id=g.current_user.id,
            lesson_id=lesson.id
        ).first()
        lessons.append(lesson.to_dict(with_progress=True, student_id=g.current_user.id))

    return jsonify({
        'success': True,
        'data': {
            'course_id': course_id,
            'course_title': course.title,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'completion_percentage': round(completion_percentage, 2),
            'lessons': lessons,
        },
    }), 200
