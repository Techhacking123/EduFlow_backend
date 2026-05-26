import random
import re
from flask import Blueprint, request, jsonify, g
from ..extensions import db, limiter, redis_client, mail
from .models import User, RefreshToken, generate_student_code
from .utils import (
    generate_access_token,
    generate_refresh_token,
    decode_refresh_token,
    revoke_refresh_token,
)
from ..middleware.auth_guard import jwt_required_custom
from flask_mail import Message

auth_bp = Blueprint('auth', __name__)

VALID_ROLES = ('student', 'faculty', 'admin', 'parent')
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')


# ---------- POST /api/v1/auth/register ----------
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    # Required fields
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', '').strip().lower()
    phone = data.get('phone')
    phone = phone.strip() if phone else None

    # Validation
    errors = []
    if not name:
        errors.append('Name is required')
    if not email or not EMAIL_REGEX.match(email):
        errors.append('A valid email is required')
    if len(password) < 8:
        errors.append('Password must be at least 8 characters')
    if role not in VALID_ROLES:
        errors.append(f'Role must be one of: {", ".join(VALID_ROLES)}')

    if errors:
        return jsonify({
            'success': False,
            'message': '; '.join(errors),
            'error_code': 'VALIDATION_ERROR',
        }), 422

    # Check uniqueness
    if User.query.filter_by(email=email).first():
        return jsonify({
            'success': False,
            'message': 'Email is already registered',
            'error_code': 'DUPLICATE_EMAIL',
        }), 409

    # Create user
    user = User(name=name, email=email, role=role, phone=phone)
    user.set_password(password)

    if role == 'student':
        # Generate a unique student code
        while True:
            code = generate_student_code()
            if not User.query.filter_by(student_code=code).first():
                user.student_code = code
                break

    db.session.add(user)
    db.session.commit()

    # Send welcome email (non-blocking — silently skip if mail not configured)
    try:
        msg = Message(
            subject='Welcome to EduFlow!',
            recipients=[email],
        )
        msg.html = (
            f'<h2>Welcome to EduFlow, {name}!</h2>'
            f'<p>Your account has been created with the role: <strong>{role}</strong>.</p>'
            f'<p>Please log in to get started.</p>'
        )
        mail.send(msg)
    except Exception:
        pass  # Mail delivery is best-effort in dev

    return jsonify({
        'success': True,
        'message': 'Registered successfully',
        'data': {
            'user_id': str(user.id),
            'email': user.email,
            'role': user.role,
            'student_code': user.student_code,
        },
    }), 201


# ---------- POST /api/v1/auth/login ----------
@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json() or {}

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({
            'success': False,
            'message': 'Email and password are required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    user = User.query.filter_by(email=email).first()

    if user is None or not user.check_password(password):
        return jsonify({
            'success': False,
            'message': 'Invalid email or password',
            'error_code': 'INVALID_CREDENTIALS',
        }), 401

    if not user.is_active:
        return jsonify({
            'success': False,
            'message': 'Account is deactivated. Contact support.',
            'error_code': 'ACCOUNT_INACTIVE',
        }), 403

    access_token = generate_access_token(user)
    refresh_token = generate_refresh_token(user)

    return jsonify({
        'success': True,
        'data': {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'student_code': user.student_code,
            },
        },
    }), 200


# ---------- POST /api/v1/auth/refresh ----------
@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    data = request.get_json() or {}
    token = data.get('refresh_token', '')

    if not token:
        return jsonify({
            'success': False,
            'message': 'Refresh token is required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    # Verify token exists in DB
    record = RefreshToken.query.filter_by(token=token).first()
    if record is None:
        return jsonify({
            'success': False,
            'message': 'Invalid refresh token',
            'error_code': 'INVALID_TOKEN',
        }), 401

    if record.is_expired():
        db.session.delete(record)
        db.session.commit()
        return jsonify({
            'success': False,
            'message': 'Refresh token has expired. Please log in again.',
            'error_code': 'TOKEN_EXPIRED',
        }), 401

    # Decode to verify signature
    payload = decode_refresh_token(token)
    if payload is None:
        revoke_refresh_token(token)
        return jsonify({
            'success': False,
            'message': 'Invalid refresh token',
            'error_code': 'INVALID_TOKEN',
        }), 401

    user = User.query.get(payload['sub'])
    if user is None or not user.is_active:
        return jsonify({
            'success': False,
            'message': 'User not found or deactivated',
            'error_code': 'UNAUTHORIZED',
        }), 401

    new_access_token = generate_access_token(user)

    return jsonify({
        'success': True,
        'data': {
            'access_token': new_access_token,
        },
    }), 200


# ---------- POST /api/v1/auth/logout ----------
@auth_bp.route('/logout', methods=['POST'])
@jwt_required_custom
def logout():
    data = request.get_json() or {}
    refresh_token = data.get('refresh_token', '')

    if refresh_token:
        revoke_refresh_token(refresh_token)
    else:
        # If no specific token supplied, revoke all tokens for the user
        RefreshToken.query.filter_by(user_id=g.current_user.id).delete()
        db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Logged out',
    }), 200


# ---------- GET /api/v1/auth/me ----------
@auth_bp.route('/me', methods=['GET'])
@jwt_required_custom
def me():
    user = g.current_user
    return jsonify({
        'success': True,
        'data': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'phone': user.phone,
            'student_code': user.student_code,
            'created_at': user.created_at.isoformat() if user.created_at else None,
        },
    }), 200

from ..middleware.role_guard import role_required

# ---------- GET /api/v1/auth/users ----------
@auth_bp.route('/users', methods=['GET'])
@jwt_required_custom
@role_required('admin')
def get_all_users():
    users = User.query.all()
    data = []
    for u in users:
        data.append({
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'created_at': u.created_at.isoformat() if u.created_at else None,
        })
    return jsonify({
        'success': True,
        'data': data
    }), 200

# ---------- DELETE /api/v1/auth/users/<id> ----------
@auth_bp.route('/users/<user_id>', methods=['DELETE'])
@jwt_required_custom
@role_required('admin')
def delete_user(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
        
    if user.id == g.current_user.id:
        return jsonify({'success': False, 'message': 'Cannot delete your own admin account'}), 400
        
    try:
        from ..payments.models import Payment
        from ..enrollments.models import Enrollment
        from ..courses.models import Course, LessonProgress, Lesson
        from ..chat.models import ChatMessage
        from ..batches.models import Batch, AttendanceLog
        
        # Delete student related records
        Enrollment.query.filter_by(student_id=user.id).delete()
        Payment.query.filter_by(student_id=user.id).delete()
        LessonProgress.query.filter_by(student_id=user.id).delete()
        ChatMessage.query.filter_by(sender_id=user.id).delete()
        AttendanceLog.query.filter_by(student_id=user.id).delete()
        
        # If user is faculty, delete courses and batches
        if user.role == 'faculty':
            batches = Batch.query.filter_by(faculty_id=user.id).all()
            for b in batches:
                Enrollment.query.filter_by(batch_id=b.id).delete()
                Payment.query.filter_by(batch_id=b.id).delete()
                AttendanceLog.query.filter_by(batch_id=b.id).delete()
                db.session.delete(b)
                
            courses = Course.query.filter_by(faculty_id=user.id).all()
            for c in courses:
                lessons = Lesson.query.filter_by(course_id=c.id).all()
                for l in lessons:
                    LessonProgress.query.filter_by(lesson_id=l.id).delete()
                    db.session.delete(l)
                db.session.delete(c)
                
        db.session.delete(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal Server Error while deleting user'}), 500
    
    return jsonify({'success': True, 'message': 'User deleted successfully'}), 200

# ---------- GET /api/v1/auth/faculties ----------
@auth_bp.route('/faculties', methods=['GET'])
@jwt_required_custom
def get_faculties():
    from ..middleware.role_guard import role_required
    if g.current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
    faculties = User.query.filter_by(role='faculty', is_active=True).all()
    result = []
    for f in faculties:
        result.append({
            'id': f.id,
            'name': f.name,
            'email': f.email
        })
        
    return jsonify({
        'success': True,
        'data': result
    }), 200


# ---------- POST /api/v1/auth/forgot-password ----------
@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
def forgot_password():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({
            'success': False,
            'message': 'Email is required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    user = User.query.filter_by(email=email).first()

    # Always return success to prevent email enumeration
    if user is None:
        return jsonify({
            'success': True,
            'message': 'If the email exists, an OTP has been sent',
        }), 200

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))

    # Store in Redis with 10-minute TTL
    redis_key = f'password_reset_otp:{email}'
    redis_client.setex(redis_key, 600, otp)

    # Send OTP via email
    try:
        msg = Message(
            subject='EduFlow — Password Reset OTP',
            recipients=[email],
        )
        msg.html = (
            f'<h2>Password Reset</h2>'
            f'<p>Your OTP is: <strong>{otp}</strong></p>'
            f'<p>This code expires in 10 minutes.</p>'
        )
        mail.send(msg)
    except Exception:
        pass  # Best-effort in dev

    return jsonify({
        'success': True,
        'message': 'OTP sent to email',
    }), 200


# ---------- POST /api/v1/auth/reset-password ----------
@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()
    new_password = data.get('new_password', '')

    if not email or not otp or not new_password:
        return jsonify({
            'success': False,
            'message': 'Email, OTP, and new password are required',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    if len(new_password) < 8:
        return jsonify({
            'success': False,
            'message': 'Password must be at least 8 characters',
            'error_code': 'VALIDATION_ERROR',
        }), 422

    # Validate OTP from Redis
    redis_key = f'password_reset_otp:{email}'
    stored_otp = redis_client.get(redis_key)

    if stored_otp is None or stored_otp != otp:
        return jsonify({
            'success': False,
            'message': 'Invalid or expired OTP',
            'error_code': 'INVALID_OTP',
        }), 401

    user = User.query.filter_by(email=email).first()
    if user is None:
        return jsonify({
            'success': False,
            'message': 'User not found',
            'error_code': 'NOT_FOUND',
        }), 404

    user.set_password(new_password)
    db.session.commit()

    # Delete OTP from Redis
    redis_client.delete(redis_key)

    # Revoke all existing refresh tokens for security
    RefreshToken.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Password reset successful',
    }), 200
