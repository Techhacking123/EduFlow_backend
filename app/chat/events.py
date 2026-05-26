from flask import request
from flask_socketio import emit
from ..extensions import socketio, db
from .models import ChatMessage
from ..auth.models import User
from flask_jwt_extended import decode_token

# Connection tracking
connected_users = {}

@socketio.on('connect')
def handle_connect():
    token = request.args.get('token')
    if not token or token == 'null':
        print("Socket connection rejected: No token")
        return False
    
    try:
        decoded_token = decode_token(token)
        user_id = decoded_token['sub']
        user = User.query.get(user_id)
        if not user:
            print("Socket connection rejected: User not found")
            return False
        
        connected_users[request.sid] = user.id
        print(f"Socket connected: {user.name}")
        emit('status', {'msg': f'{user.name} has joined the chat.'}, broadcast=True)
    except Exception as e:
        print("Socket connection error:", e)
        return False

@socketio.on('disconnect')
def handle_disconnect():
    user_id = connected_users.pop(request.sid, None)
    if user_id:
        user = User.query.get(user_id)
        if user:
            emit('status', {'msg': f'{user.name} has left the chat.'}, broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    user_id = connected_users.get(request.sid)
    if not user_id:
        return
    
    content = data.get('content', '').strip()
    image_url = data.get('image_url', '').strip()
    
    if not content and not image_url:
        return
        
    msg = ChatMessage(
        sender_id=user_id,
        content=content if content else None,
        image_url=image_url if image_url else None
    )
    db.session.add(msg)
    db.session.commit()
    
    emit('receive_message', msg.to_dict(), broadcast=True)
