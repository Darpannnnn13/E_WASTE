from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from mongo import mongo
from bson import ObjectId
from services.payment_service import PaymentService
import uuid

payment_bp = Blueprint('payment', __name__)
payment_service = PaymentService()

@payment_bp.route('/payment/initiate/<pickup_id>', methods=['POST'])
def initiate_payment(pickup_id):
    """Create a payment order for a pickup request"""
    if session.get('role') != 'recycler':
        return jsonify({'error': 'Unauthorized'}), 403

    pickup = mongo.db.pickup_requests.find_one({'_id': ObjectId(pickup_id)})
    if not pickup:
        return jsonify({'error': 'Pickup not found'}), 404

    # Determine amount (use engineer_price or calculate fallback)
    amount = pickup.get('engineer_price')
    if not amount:
        # Fallback logic if no price set (e.g. 50 INR per kg)
        weight = pickup.get('final_weight') or pickup.get('approx_weight') or 0
        amount = weight * 0.05 # Assuming weight is in grams, 50 INR/kg = 0.05 INR/g
        if amount < 1: amount = 100 # Minimum amount

    order = payment_service.create_order(amount, pickup_id)
    
    if not order:
        return jsonify({'error': 'Failed to create payment order'}), 500

    return jsonify({
        'order_id': order['id'],
        'amount': order['amount'],
        'key_id': payment_service.key_id,
        'pickup_id': str(pickup_id),
        'user_name': pickup.get('user_name'),
        'email': session.get('email')
    })


@payment_bp.route('/payment/verify', methods=['POST'])
def verify_payment():
    """Handle payment success callback"""
    data = request.json
    
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_signature = data.get('razorpay_signature')
    pickup_id = data.get('pickup_id')

    # Verify Signature
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }
    
    if payment_service.verify_signature(params_dict):
        # Calculate total amount from order (convert paise to INR)
        # In a real scenario, fetch order details from Razorpay to confirm amount
        # Here we trust the passed amount or re-fetch from DB
        pickup = mongo.db.pickup_requests.find_one({'_id': ObjectId(pickup_id)})
        amount = pickup.get('engineer_price') or 100 # Fallback

        # Distribute Funds & Generate Invoices
        success = payment_service.distribute_and_generate_invoices(
            pickup_id, amount, razorpay_payment_id
        )
        
        if success:
            return jsonify({'success': True})
    
    return jsonify({'error': 'Payment verification failed'}), 400


# ============ SIMULATED PAYMENT ROUTES ============

@payment_bp.route('/payment/preview/<pickup_id>', methods=['GET'])
def preview_payment(pickup_id):
    """Get payment details and split breakdown for the modal"""
    if session.get('role') != 'recycler':
        return jsonify({'error': 'Unauthorized'}), 403

    pickup = mongo.db.pickup_requests.find_one({'_id': ObjectId(pickup_id)})
    if not pickup:
        return jsonify({'error': 'Pickup not found'}), 404

    # Determine amount (Automated price logic)
    amount = pickup.get('engineer_price')
    if not amount:
        weight = pickup.get('final_weight') or pickup.get('approx_weight') or 0
        amount = weight * 0.05 # Fallback calculation
        if amount < 1: amount = 100

    # Calculate splits for display
    splits = {
        'user': round(amount * 0.50, 2),
        'driver': round(amount * 0.10, 2),
        'engineer': round(amount * 0.15, 2),
        'warehouse': round(amount * 0.25, 2)
    }

    return jsonify({
        'pickup_id': str(pickup_id),
        'amount': amount,
        'splits': splits,
        'user_name': pickup.get('user_name', 'Unknown')
    })

@payment_bp.route('/payment/confirm-simulated', methods=['POST'])
def confirm_simulated_payment():
    """Process the simulated payment and generate invoices"""
    data = request.json
    pickup_id = data.get('pickup_id')
    
    # Fetch amount again to be safe
    preview_response = preview_payment(pickup_id)
    if preview_response.status_code != 200:
        return preview_response
    
    amount = preview_response.json['amount']
    transaction_id = f"TXN_SIM_{uuid.uuid4().hex[:12].upper()}"
    
    success = payment_service.distribute_and_generate_invoices(
        pickup_id, amount, transaction_id
    )
    
    if success:
        return jsonify({'success': True, 'transaction_id': transaction_id})
    return jsonify({'error': 'Payment processing failed'}), 500


@payment_bp.route('/invoices')
def my_invoices():
    """View invoices for the logged-in user"""
    if 'user_id' not in session:
        return redirect('/')
    
    user_id = session['user_id']
    role = session.get('role')
    
    query = {'recipient_id': user_id}
    if role == 'warehouse':
        # Warehouse sees their own + can see all (optional)
        query = {'$or': [{'recipient_id': user_id}, {'recipient_role': 'warehouse'}]}
        
    invoices = list(mongo.db.invoices.find(query).sort('created_at', -1))
    
    # 2. Pending / In-Process Items (Not yet recycled/paid)
    pending_items = []
    
    if role == 'user':
        # Handle both ObjectId and string user_id
        try:
            user_query = {'$or': [{'user_id': user_id}, {'user_id': ObjectId(user_id)}]}
        except:
            user_query = {'user_id': user_id}
            
        # Add status filter (anything not recycled is technically pending payment if it's in the system)
        user_query['status'] = {'$ne': 'recycled'}
        pending_items = list(mongo.db.pickup_requests.find(user_query).sort('created_at', -1))

    elif role == 'engineer':
        # Engineers see requests assigned to them
        pending_items = list(mongo.db.pickup_requests.find({
            'engineer_id': user_id,
            'status': {'$ne': 'recycled'}
        }).sort('created_at', -1))

    elif role == 'driver':
        # Drivers see requests in their clusters
        clusters = list(mongo.db.collection_clusters.find({'driver_id': user_id}))
        pickup_ids = []
        for c in clusters:
            for u in c.get('users', []):
                pickup_ids.append(u['user_id'])
        
        if pickup_ids:
            pending_items = list(mongo.db.pickup_requests.find({
                '_id': {'$in': pickup_ids},
                'status': {'$ne': 'recycled'}
            }).sort('created_at', -1))

    elif role == 'warehouse':
        # Warehouse sees items collected but not yet recycled (waiting for payment)
        pending_items = list(mongo.db.pickup_requests.find({
            'status': 'collected'
        }).sort('updated_at', -1))

    # Calculate estimated earnings for pending items
    for item in pending_items:
        # Determine base amount
        amount = item.get('engineer_price')
        if not amount:
            weight = item.get('final_weight') or item.get('approx_weight') or 0
            try:
                weight = float(weight)
            except (ValueError, TypeError):
                weight = 0
            amount = weight * 0.05 # Fallback: 50 INR/kg -> 0.05 INR/g
            if amount < 100: amount = 100
        
        # Calculate share based on role
        shares = {'user': 0.50, 'driver': 0.10, 'engineer': 0.15, 'warehouse': 0.25}
        role_key = role if role in shares else 'user'
        item['estimated_share'] = round(amount * shares.get(role_key, 0), 2)
        item['share_percentage'] = f"{int(shares.get(role_key, 0) * 100)}%"
            
    return render_template('payment/invoices.html', invoices=invoices, pending_items=pending_items, role=role)