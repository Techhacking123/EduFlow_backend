import razorpay
from flask import current_app


def get_razorpay_client():
    return razorpay.Client(auth=(
        current_app.config['RAZORPAY_KEY_ID'],
        current_app.config['RAZORPAY_KEY_SECRET']
    ))


def create_razorpay_order(amount_rupees, receipt_id):
    client = get_razorpay_client()
    order = client.order.create({
        'amount': int(amount_rupees * 100),
        'currency': 'INR',
        'receipt': str(receipt_id),
        'payment_capture': 1
    })
    return order


def verify_payment_signature(order_id, payment_id, signature):
    import hmac
    import hashlib
    
    key = current_app.config['RAZORPAY_KEY_SECRET'].encode()
    msg = f"{order_id}|{payment_id}".encode()
    
    generated_signature = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(generated_signature, signature)
