from marshmallow import Schema, fields


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
    is_free = fields.Bool(load_default=False)
    status = fields.Str(allow_none=True, load_default='upcoming')
    created_at = fields.DateTime(dump_only=True)


batch_schema = BatchSchema()
batches_schema = BatchSchema(many=True)