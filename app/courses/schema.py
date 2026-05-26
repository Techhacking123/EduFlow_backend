from marshmallow import Schema, fields


class CourseSchema(Schema):
    id = fields.UUID(dump_only=True)
    institute_id = fields.UUID(allow_none=True)
    created_by = fields.UUID(required=True)
    title = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    category = fields.Str(allow_none=True)
    thumbnail_url = fields.Str(allow_none=True)
    is_published = fields.Bool(load_default=False)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class LessonSchema(Schema):
    id = fields.UUID(dump_only=True)
    course_id = fields.UUID(required=True)
    title = fields.Str(required=True)
    type = fields.Str(required=True)
    content_url = fields.Str(allow_none=True)
    content_text = fields.Str(allow_none=True)
    position = fields.Int(allow_none=True, load_default=0)
    duration_mins = fields.Int(allow_none=True)
    is_preview = fields.Bool(load_default=False)
    quiz_options = fields.Dict(allow_none=True)
    quiz_correct_answer = fields.Str(allow_none=True)
    live_start_time = fields.DateTime(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class LessonProgressSchema(Schema):
    id = fields.UUID(dump_only=True)
    student_id = fields.UUID(required=True)
    lesson_id = fields.UUID(required=True)
    is_completed = fields.Bool(load_default=False)
    quiz_selected_option = fields.Str(allow_none=True)
    completed_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class LessonSchema(Schema):
    id = fields.UUID(dump_only=True)
    course_id = fields.UUID(required=True)
    title = fields.Str(required=True)
    type = fields.Str(required=True)
    content_url = fields.Str(allow_none=True)
    content_text = fields.Str(allow_none=True)
    position = fields.Int(allow_none=True, load_default=0)
    duration_mins = fields.Int(allow_none=True)
    is_preview = fields.Bool()
    quiz_options = fields.Dict(allow_none=True)
    quiz_correct_answer = fields.Str(allow_none=True)
    live_start_time = fields.DateTime(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class LessonProgressSchema(Schema):
    id = fields.UUID(dump_only=True)
    student_id = fields.UUID(required=True)
    lesson_id = fields.UUID(required=True)
    is_completed = fields.Bool()
    quiz_selected_option = fields.Str(allow_none=True)
    completed_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class BatchSchema(Schema):
    id = fields.UUID(dump_only=True)
    course_id = fields.UUID(required=True)
    faculty_id = fields.UUID(required=True)
    name = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    max_students = fields.Int(allow_none=True, load_default=50)
    price = fields.Decimal(as_string=True, allow_none=True, load_default='0.00')
    is_free = fields.Bool()
    status = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class EnrollmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    student_id = fields.UUID(required=True)
    batch_id = fields.UUID(required=True)
    payment_id = fields.UUID(allow_none=True)
    status = fields.Str(allow_none=True)
    is_paid = fields.Bool()
    enrolled_at = fields.DateTime(dump_only=True)
    approved_at = fields.DateTime(allow_none=True)


class PaymentSchema(Schema):
    id = fields.UUID(dump_only=True)
    student_id = fields.UUID(required=True)
    batch_id = fields.UUID(required=True)
    amount = fields.Decimal(as_string=True, required=True)
    currency = fields.Str(allow_none=True)
    status = fields.Str(allow_none=True)
    razorpay_order_id = fields.UUID(allow_none=True)
    razorpay_payment_id = fields.UUID(allow_none=True)
    razorpay_signature = fields.Str(allow_none=True)
    paid_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


course_schema = CourseSchema()
courses_schema = CourseSchema(many=True)

lesson_schema = LessonSchema()
lessons_schema = LessonSchema(many=True)

lesson_progress_schema = LessonProgressSchema()
lesson_progresses_schema = LessonProgressSchema(many=True)

batch_schema = BatchSchema()
batches_schema = BatchSchema(many=True)

enrollment_schema = EnrollmentSchema()
enrollments_schema = EnrollmentSchema(many=True)

payment_schema = PaymentSchema()
payments_schema = PaymentSchema(many=True)
