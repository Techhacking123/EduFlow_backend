from functools import wraps
from flask import g, jsonify


def role_required(*allowed_roles):
    """Decorator to enforce role-based access control.

    Must be used **after** ``@jwt_required_custom`` so that
    ``g.current_user`` is already populated.

    Usage::

        @jwt_required_custom
        @role_required('admin', 'faculty')
        def admin_or_faculty_view():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import request
            if request.method == 'OPTIONS':
                return f(*args, **kwargs)
                
            current_user = getattr(g, 'current_user', None)

            if current_user is None:
                return jsonify({
                    'success': False,
                    'message': 'Authentication required',
                    'error_code': 'UNAUTHORIZED',
                }), 401

            if current_user.role not in allowed_roles:
                return jsonify({
                    'success': False,
                    'message': 'You do not have permission to access this resource',
                    'error_code': 'FORBIDDEN',
                }), 403

            return f(*args, **kwargs)

        return decorated
    return decorator
