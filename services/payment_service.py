import os
from datetime import datetime
from bson import ObjectId
from mongo import mongo

# Try importing razorpay, handle if not installed
try:
    import razorpay
except ImportError:
    razorpay = None

class PaymentService:
    def __init__(self):
        # Use environment variables for keys
        self.key_id = os.getenv('RAZORPAY_KEY_ID')
        self.key_secret = os.getenv('RAZORPAY_KEY_SECRET')
        
        if not self.key_id or not self.key_secret or self.key_id.startswith('paste_your'):
            print("INFO: Razorpay keys not found. Using Simulated Payment Gateway mode.")
            self.key_id = 'rzp_test_123456789'
            self.key_secret = 'secret_123456789'
        
        if razorpay and self.key_id != 'rzp_test_123456789':
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
        else:
            self.client = None

    def create_order(self, amount_inr, receipt_id):
        """Create a Razorpay order"""
        amount_paise = int(amount_inr * 100)
        
        if self.client:
            try:
                order = self.client.order.create({
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": str(receipt_id),
                    "payment_capture": 1
                })
                return order
            except Exception as e:
                print(f"Razorpay Error: {e}")
                return None
        else:
            # Mock order for testing without API keys
            return {
                "id": f"order_mock_{int(datetime.now().timestamp())}",
                "amount": amount_paise,
                "currency": "INR",
                "receipt": str(receipt_id),
                "status": "created"
            }

    def verify_signature(self, params):
        """Verify Razorpay signature"""
        if self.client:
            try:
                self.client.utility.verify_payment_signature(params)
                return True
            except Exception:
                return False
        return True # Always true for mock

    def distribute_and_generate_invoices(self, pickup_id, total_amount, transaction_id):
        """
        Distribute funds: 50% User, 10% Driver, 15% Engineer, 25% Warehouse
        Generate invoices for each.
        """
        pickup = mongo.db.pickup_requests.find_one({'_id': ObjectId(pickup_id)})
        if not pickup:
            return False

        # 1. Identify Stakeholders
        user_id = pickup.get('user_id')
        engineer_id = pickup.get('engineer_id')
        
        # Find driver via cluster
        driver_id = None
        if pickup.get('cluster_id'):
            cluster = mongo.db.collection_clusters.find_one({'_id': ObjectId(pickup['cluster_id'])})
            if cluster:
                driver_id = cluster.get('driver_id')

        # 2. Calculate Splits
        share_user = round(total_amount * 0.50, 2)
        share_driver = round(total_amount * 0.10, 2)
        share_engineer = round(total_amount * 0.15, 2)
        
        # If driver/engineer missing, add their share to warehouse
        warehouse_base = 0.25
        if not driver_id: warehouse_base += 0.10
        if not engineer_id: warehouse_base += 0.15
        
        share_warehouse = round(total_amount * warehouse_base, 2)

        # 3. Generate Invoices
        timestamp = datetime.utcnow()
        invoices = []

        # Helper to create invoice doc
        def create_invoice(recipient_id, role, amount, pct):
            return {
                'invoice_number': f"INV-{int(timestamp.timestamp())}-{role[:3].upper()}",
                'recipient_id': str(recipient_id) if recipient_id else 'WAREHOUSE_ADMIN',
                'recipient_role': role,
                'amount': amount,
                'currency': 'INR',
                'percentage': f"{int(pct*100)}%",
                'pickup_id': str(pickup_id),
                'transaction_id': transaction_id,
                'status': 'paid',
                'created_at': timestamp,
                'description': f"Payout for E-Waste Collection: {pickup.get('ewaste_type', 'Item')}"
            }

        # User Invoice
        if user_id:
            invoices.append(create_invoice(user_id, 'user', share_user, 0.50))
            # Update user wallet (optional)
            mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$inc': {'wallet_balance': share_user}})

        # Driver Invoice
        if driver_id:
            invoices.append(create_invoice(driver_id, 'driver', share_driver, 0.10))
            mongo.db.users.update_one({'_id': ObjectId(driver_id)}, {'$inc': {'wallet_balance': share_driver}})

        # Engineer Invoice
        if engineer_id:
            invoices.append(create_invoice(engineer_id, 'engineer', share_engineer, 0.15))
            mongo.db.users.update_one({'_id': ObjectId(engineer_id)}, {'$inc': {'wallet_balance': share_engineer}})

        # Warehouse Invoice
        invoices.append(create_invoice(None, 'warehouse', share_warehouse, warehouse_base))

        # 4. Save to MongoDB
        if invoices:
            mongo.db.invoices.insert_many(invoices)

        # 5. Update Pickup Status
        mongo.db.pickup_requests.update_one(
            {'_id': ObjectId(pickup_id)},
            {'$set': {'status': 'recycled', 'payment_status': 'paid', 'paid_amount': total_amount}}
        )

        return True