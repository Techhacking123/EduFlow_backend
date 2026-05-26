from functools import wraps
from flask import request, g, jsonify
from ..auth.utils import decode_access_token
from ..auth.models import User


def jwt_required_custom(f):
    """Custom decorator to enforce JWT authentication.

    Reads the Authorization header, verifies the access token,
    and attaches the current user to Flask's ``g`` object.
    Returns 401 if the token is missing, invalid, or expired.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
            
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'message': 'Missing or invalid authorization header',
                'error_code': 'UNAUTHORIZED',
            }), 401

        token = auth_header.split(' ', 1)[1]
        payload = decode_access_token(token)

        if payload is None:
            return jsonify({
                'success': False,
                'message': 'Invalid or expired access token',
                'error_code': 'UNAUTHORIZED',
            }), 401

        user = User.query.get(payload['sub'])
        if user is None or not user.is_active:
            return jsonify({
                'success': False,
                'message': 'User not found or deactivated',
                'error_code': 'UNAUTHORIZED',
            }), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated

def jwt_optional_custom(f):
    """Optional JWT auth. Sets g.current_user if valid token present, else None."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
            
        g.current_user = None
        auth_header = request.headers.get('Authorization', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            payload = decode_access_token(token)
            if payload:
                user = User.query.get(payload['sub'])
                if user and user.is_active:
                    g.current_user = user
                    
        return f(*args, **kwargs)

    return decorated
