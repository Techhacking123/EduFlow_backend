from marshmallow import Schema, fields


class PaymentSchema(Schema):
    id = fields.UUID(dump_only=True)
    student_id = fields.UUID(required=True)
    batch_id = fields.UUID(required=True)
    amount = fields.Decimal(as_string=True, required=True)
    currency = fields.Str(allow_none=True, load_default='INR')
    status = fields.Str(allow_none=True, load_default='pending')
    razorpay_order_id = fields.UUID(allow_none=True)
    razorpay_payment_id = fields.UUID(allow_none=True)
    razorpay_signature = fields.Str(allow_none=True)
    paid_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


payment_schema = PaymentSchema()
payments_schema = PaymentSchema(many=True)