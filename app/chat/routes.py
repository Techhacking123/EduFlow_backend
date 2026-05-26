from flask import Blueprint, jsonify
from ..middleware.auth_guard import jwt_required_custom
from .models import ChatMessage

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/history', methods=['GET'])
@jwt_required_custom
def get_chat_history():
    # Fetch last 100 messages
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).limit(100).all()
    # Reverse to return in chronological order
    messages.reverse()
    
    return jsonify({
        'success': True,
        'data': [msg.to_dict() for msg in messages]
    }), 200
