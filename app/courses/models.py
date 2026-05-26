import uuid
from datetime import datetime
from ..extensions import db
from ..auth.models import User


class Course(db.Model):
    """Course model - created by admin/faculty, contains lessons and batches."""
    __tablename__ = 'courses'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    institute_id = db.Column(db.UUID(as_uuid=True), nullable=True)
    created_by = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('users.id'),
        nullable=False,
    )
    created_by_user = db.relationship(
        'User',
        foreign_keys=[created_by],
        lazy=True,
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    thumbnail_url = db.Column(db.String(500))
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    lessons = db.relationship(
        'Lesson',
        backref='course',
        lazy=True,
        order_by='Lesson.position',
        cascade='all, delete-orphan',
    )
    batches = db.relationship(
        'Batch',
        backref='course',
        lazy=True,
        cascade='all, delete-orphan',
    )

    def to_dict(self):
        """Serialize course to dictionary."""
        return {
            'id': str(self.id),
            'created_by': str(self.created_by) if self.created_by else None,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'thumbnail_url': self.thumbnail_url,
            'is_published': self.is_published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Course {self.title}>'


class Lesson(db.Model):
    """Lesson model - individual learning unit within a course."""
    __tablename__ = 'lessons'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('courses.id'),
        nullable=False,
    )
    title = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    content_url = db.Column(db.String(500))
    content_text = db.Column(db.Text)
    position = db.Column(db.Integer, default=0)
    duration_mins = db.Column(db.Integer)
    is_preview = db.Column(db.Boolean, default=False)
    quiz_options = db.Column(db.JSON, nullable=True)
    quiz_correct_answer = db.Column(db.String(10), nullable=True)
    live_start_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    VALID_TYPES = ('video', 'document', 'text', 'assignment', 'live_class')

    def to_dict(self, with_progress=False, student_id=None):
        """Serialize lesson to dictionary."""
        data = {
            'id': str(self.id),
            'course_id': str(self.course_id),
            'title': self.title,
            'type': self.type,
            'content_url': self.content_url,
            'content_text': self.content_text,
            'position': self.position,
            'duration_mins': self.duration_mins,
            'is_preview': self.is_preview,
            'quiz_options': self.quiz_options,
            'quiz_correct_answer': self.quiz_correct_answer,
            'live_start_time': (self.live_start_time.isoformat() + 'Z') if self.live_start_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        if with_progress and student_id:
            progress = LessonProgress.query.filter_by(
                student_id=student_id,
                lesson_id=self.id
            ).first()
            data['is_completed'] = progress.is_completed if progress else False
            data['quiz_selected_option'] = progress.quiz_selected_option if progress else None
            data['completed_at'] = progress.completed_at.isoformat() if progress and progress.completed_at else None

        return data

    def __repr__(self):
        return f'<Lesson {self.title}>'


class LessonProgress(db.Model):
    """Tracks student progress on lessons."""
    __tablename__ = 'lesson_progress'

    id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    student_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('users.id'),
        nullable=False,
    )
    lesson_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('lessons.id'),
        nullable=False,
    )
    is_completed = db.Column(db.Boolean, default=False)
    quiz_selected_option = db.Column(db.String(10), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'lesson_id'),
    )

    def to_dict(self):
        """Serialize lesson progress to dictionary."""
        return {
            'id': str(self.id),
            'student_id': str(self.student_id),
            'lesson_id': str(self.lesson_id),
            'is_completed': self.is_completed,
            'quiz_selected_option': self.quiz_selected_option,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<LessonProgress student_id={self.student_id} lesson_id={self.lesson_id}>'
