from flask import Blueprint, render_template, request, redirect, session, flash
from mongo import mongo
from datetime import datetime

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/dashboard')
def dashboard():
    if session.get('role') != 'user':
        return redirect('/')

    # Fetch requests for this user, sorted by newest first
    requests = mongo.db.pickup_requests.find(
        {'user_id': session['user_id']}
    ).sort('created_at', -1)

    return render_template(
        'user/request_pickup.html',
        requests=requests
    )

@user_bp.route('/request', methods=['POST'])
def create_request():
    if session.get('role') != 'user':
        return redirect('/')

    try:
        # 1. Handle Multiple Items (Arrays from form)
        types = request.form.getlist('ewaste_type[]')
        weights = request.form.getlist('weight[]')
        item_descs = request.form.getlist('item_description[]')
        
        # 2. Calculate Total Weight
        total_weight = 0
        for w in weights:
            if w and w.strip():
                total_weight += int(w)
        
        if total_weight <= 0:
            raise ValueError("Total weight must be positive")

        # 3. Aggregate Data for Schema Compatibility
        # Join types: "PC, Battery, Monitor"
        final_ewaste_type = ", ".join([t for t in types if t.strip()])
        
        # Create detailed description breakdown
        general_desc = request.form.get('description', '')
        details = "; ".join([f"{t} ({w}g): {d}" for t, w, d in zip(types, weights, item_descs) if t])
        final_description = f"{general_desc}\n[Details]: {details}" if details else general_desc

        # Create structured items list for database
        items = []
        for t, w, d in zip(types, weights, item_descs):
            if t.strip():
                items.append({
                    'type': t.strip(),
                    'weight': int(w) if w and w.strip() else 0,
                    'description': d.strip()
                })

        # Get coordinates safely
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')

        data = {
            'user_id': session['user_id'],
            'area': request.form.get('area'),
            'address': request.form.get('address'),
            'ewaste_type': final_ewaste_type,
            'description': final_description,
            'approx_weight': total_weight,
            'items': items,
            'latitude': float(lat) if lat else None,
            'longitude': float(lng) if lng else None,
            'images': [],   # future: file upload
            'status': 'pending',
            'engineer_price': None,
            'created_at': datetime.utcnow()
        }

        mongo.db.pickup_requests.insert_one(data)
        flash('Pickup request submitted successfully', 'success')

    except ValueError:
        flash('Invalid weight provided', 'error')

    return redirect('/user/dashboard')
