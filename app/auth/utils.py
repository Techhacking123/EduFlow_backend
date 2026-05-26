import uuid
import jwt as pyjwt
from datetime import datetime, timedelta
from flask import current_app
from ..extensions import db
from .models import RefreshToken


def generate_access_token(user):
    """Generate a short-lived JWT access token."""
    expires_seconds = int(
        current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds()
    )
    payload = {
        'sub': str(user.id),
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(seconds=expires_seconds),
        'type': 'access',
    }
    token = pyjwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256',
    )
    return token


def generate_refresh_token(user):
    """Generate a long-lived refresh token and persist it in the database."""
    expires_seconds = int(
        current_app.config['JWT_REFRESH_TOKEN_EXPIRES'].total_seconds()
    )
    expires_at = datetime.utcnow() + timedelta(seconds=expires_seconds)

    payload = {
        'sub': str(user.id),
        'jti': str(uuid.uuid4()),
        'iat': datetime.utcnow(),
        'exp': expires_at,
        'type': 'refresh',
    }
    token = pyjwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256',
    )

    # Persist to database
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
    )
    db.session.add(refresh_token_record)
    db.session.commit()

    return token


def decode_access_token(token):
    """Decode and validate an access token. Returns payload dict or None."""
    try:
        payload = pyjwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256'],
        )
        if payload.get('type') != 'access':
            return None
        return payload
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
        return None


def decode_refresh_token(token):
    """Decode and validate a refresh token. Returns payload dict or None."""
    try:
        payload = pyjwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256'],
        )
        if payload.get('type') != 'refresh':
            return None
        return payload
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
        return None


def revoke_refresh_token(token):
    """Delete a refresh token from the database."""
    record = RefreshToken.query.filter_by(token=token).first()
    if record:
        db.session.delete(record)
        db.session.commit()
        return True
    return False


def revoke_all_user_tokens(user_id):
    """Delete all refresh tokens for a given user."""
    RefreshToken.query.filter_by(user_id=user_id).delete()
    db.session.commit()
