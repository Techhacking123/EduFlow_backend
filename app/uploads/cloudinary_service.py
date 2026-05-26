import cloudinary
import cloudinary.uploader
from flask import current_app


def configure_cloudinary():
    """Configure Cloudinary with settings from app config."""
    cloudinary.config(
        cloud_name=current_app.config['CLOUDINARY_CLOUD_NAME'],
        api_key=current_app.config['CLOUDINARY_API_KEY'],
        api_secret=current_app.config['CLOUDINARY_API_SECRET']
    )


def upload_file(file, folder='lms-uploads'):
    """Upload a file to Cloudinary, with a local fallback for offline development.
    
    Args:
        file: File object from request.files
        folder: Cloudinary folder name (default: 'lms-uploads')
    
    Returns:
        dict with url, public_id, and resource_type
    """
    if current_app.config.get('CLOUDINARY_API_KEY') == 'dummy_key':
        import os
        import uuid
        from werkzeug.utils import secure_filename
        
        # Determine static directory
        static_dir = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(static_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_name = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        
        file_path = os.path.join(static_dir, unique_name)
        file.seek(0)
        file.save(file_path)
        
        url = f"http://localhost:5000/static/uploads/{unique_name}"
        return {
            'url': url,
            'public_id': unique_name,
            'resource_type': 'video' if ext.lower() in ('.mp4', '.mov', '.avi') else 'image' if ext.lower() in ('.jpg', '.jpeg', '.png') else 'raw'
        }

    configure_cloudinary()
    
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type='auto'
    )
    
    return {
        'url': result['secure_url'],
        'public_id': result['public_id'],
        'resource_type': result['resource_type'],
    }


def delete_file(public_id, folder='lms-uploads'):
    """Delete a file from Cloudinary.
    
    Args:
        public_id: Cloudinary public ID of the file
        folder: Cloudinary folder name
    
    Returns:
        dict with delete result
    """
    configure_cloudinary()
    
    result = cloudinary.uploader.destroy(
        f"{folder}/{public_id}"
    )
    
    return result
