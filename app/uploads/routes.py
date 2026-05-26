from flask import Blueprint, request, jsonify, g
from ..extensions import db
from ..middleware.auth_guard import jwt_required_custom
from ..middleware.role_guard import role_required
from .cloudinary_service import upload_file

uploads_bp = Blueprint('uploads', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'ppt', 'pptx', 'mp4', 'mov', 'avi', 'mkv'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@uploads_bp.route('/file', methods=['POST'])
@jwt_required_custom
def upload_file_endpoint():
    """POST /api/v1/uploads/file - Upload a file to Cloudinary."""
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'message': 'No file uploaded',
            'error_code': 'NO_FILE',
        }), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({
            'success': False,
            'message': 'No file selected',
            'error_code': 'NO_FILENAME',
        }), 400

    file_ext = file.filename.rsplit('.', 1)[-1].lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            'success': False,
            'message': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
            'error_code': 'INVALID_FILE_TYPE',
        }), 400

    if file.content_length and file.content_length > MAX_FILE_SIZE:
        return jsonify({
            'success': False,
            'message': f'File size exceeds 20 MB limit',
            'error_code': 'FILE_TOO_LARGE',
        }), 400

    try:
        result = upload_file(file)
        
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'data': {
                'url': result['url'],
                'public_id': result['public_id'],
                'resource_type': result['resource_type'],
            },
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Upload failed: {str(e)}',
            'error_code': 'UPLOAD_FAILED',
        }), 500
