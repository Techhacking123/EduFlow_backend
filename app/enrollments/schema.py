from marshmallow import Schema, fields


class EnrollmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    student_id = fields.UUID(required=True)
    batch_id = fields.UUID(required=True)
    payment_id = fields.UUID(allow_none=True)
    status = fields.Str(allow_none=True, load_default='pending')
    is_paid = fields.Bool(load_default=False)
    enrolled_at = fields.DateTime(dump_only=True)
    approved_at = fields.DateTime(allow_none=True)


enrollment_schema = EnrollmentSchema()
enrollments_schema = EnrollmentSchema(many=True)