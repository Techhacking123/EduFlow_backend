from ..extensions import db
import uuid

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.now(), nullable=False)

    sender = db.relationship('User', backref='chat_messages')

    def to_dict(self):
        return {
            'id': str(self.id) if self.id else None,
            'sender_id': str(self.sender_id) if self.sender_id else None,
            'sender_name': self.sender.name if self.sender else 'Unknown',
            'sender_role': self.sender.role if self.sender else 'student',
            'content': self.content,
            'image_url': self.image_url,
            'timestamp': self.timestamp.isoformat() + 'Z' if self.timestamp else None
        }
