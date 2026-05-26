import os
from flask import Flask, jsonify
from .config import config_by_name
from .extensions import db, migrate, jwt, mail, bcrypt, cors, limiter, socketio


def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app)
    # Parse allowed origins from env (comma-separated)
    raw_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173')
    allowed_origins = [o.strip() for o in raw_origins.split(',') if o.strip()]

    cors.init_app(app, resources={
        r"/api/.*": {
            "origins": allowed_origins,
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
        }
    })

    # Register blueprints
    from .auth.routes import auth_bp
    from .courses.routes import courses_bp
    from .batches.routes import batches_bp
    from .enrollments.routes import enrollments_bp
    from .payments.routes import payments_bp
    from .uploads.routes import uploads_bp
    from .chat.routes import chat_bp
    from .parent.routes import parent_bp

    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(courses_bp, url_prefix='/api/v1/courses')
    app.register_blueprint(batches_bp, url_prefix='/api/v1/batches')
    app.register_blueprint(enrollments_bp, url_prefix='/api/v1/enrollments')
    app.register_blueprint(payments_bp, url_prefix='/api/v1/payments')
    app.register_blueprint(uploads_bp, url_prefix='/api/v1/uploads')
    app.register_blueprint(chat_bp, url_prefix='/api/v1/chat')
    app.register_blueprint(parent_bp, url_prefix='/api/v1/parent')

    # Register socket events
    from .chat import events

    # Register global error handlers
    _register_error_handlers(app)


    return app


def _register_error_handlers(app):
    """Register global JSON error handlers."""

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({
            'success': False,
            'message': str(e.description) if hasattr(e, 'description') else 'Bad request',
            'error_code': 'BAD_REQUEST',
        }), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({
            'success': False,
            'message': str(e.description) if hasattr(e, 'description') else 'Unauthorized',
            'error_code': 'UNAUTHORIZED',
        }), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({
            'success': False,
            'message': str(e.description) if hasattr(e, 'description') else 'Forbidden',
            'error_code': 'FORBIDDEN',
        }), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            'success': False,
            'message': str(e.description) if hasattr(e, 'description') else 'Not found',
            'error_code': 'NOT_FOUND',
        }), 404

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({
            'success': False,
            'message': str(e.description) if hasattr(e, 'description') else 'Unprocessable entity',
            'error_code': 'UNPROCESSABLE_ENTITY',
        }), 422

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({
            'success': False,
            'message': 'Too many requests. Please try again later.',
            'error_code': 'RATE_LIMIT_EXCEEDED',
        }), 429

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({
            'success': False,
            'message': 'Internal server error',
            'error_code': 'INTERNAL_SERVER_ERROR',
        }), 500
