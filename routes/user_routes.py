from flask import Blueprint, render_template, request, redirect, session, flash
from mongo import mongo
from datetime import datetime
from bson import ObjectId
import math

user_bp = Blueprint('user', __name__, url_prefix='/user')


@user_bp.route('/dashboard')
def dashboard():
    if session.get('role') != 'user':
        return redirect('/')

    # Handle both ObjectId and email-based user_id (for demo users)
    user_id = session['user_id']
    try:
        from bson import ObjectId
        user_query = {'$or': [{'user_id': user_id}, {'user_id': ObjectId(user_id)}]}
    except Exception:
        user_query = {'user_id': user_id}

    # Fetch requests for this user, sorted by newest first
    requests = list(mongo.db.pickup_requests.find(user_query).sort('created_at', -1))

    # Calculate total weight for profile panel
    pipeline = [
        {'$match': user_query},
        {'$group': {'_id': None, 'total': {'$sum': {'$ifNull': ['$approx_weight', '$ewaste_weight']}}}}
    ]
    weight_res = list(mongo.db.pickup_requests.aggregate(pipeline))
    total_donated = weight_res[0]['total'] if weight_res else 0

    # Rewards: 1 Point per 100g
    points = int(total_donated / 100)

    # Leaderboard: Top 5 users by total weight
    leaderboard_pipeline = [
        {'$group': {'_id': '$user_name', 'total_weight': {'$sum': {'$ifNull': ['$approx_weight', '$ewaste_weight']}}}},
        {'$sort': {'total_weight': -1}},
        {'$limit': 5}
    ]
    leaderboard = list(mongo.db.pickup_requests.aggregate(leaderboard_pipeline))

    # Define available rewards (for example)
    rewards = [
        {'name': '10% Discount Coupon', 'cost': 500, 'code': 'ECO10'},
        {'name': 'Free E-Waste Pickup', 'cost': 1000, 'code': 'ECOFREE'},
        {'name': 'Sustainable Gift Pack', 'cost': 2000, 'code': 'ECOGIFT'}
    ]

    # Determine which rewards user can afford
    affordable_rewards = []
    for reward in rewards:
        if points >= reward['cost']:
            affordable_rewards.append(reward)

    return render_template(
        'user/dashboard.html',
        requests=requests,
        total_donated=total_donated,
        points=points,
        leaderboard=leaderboard,
        rewards=affordable_rewards)

@user_bp.route('/request', methods=['GET', 'POST'])
def create_request():
    if session.get('role') != 'user':
        return redirect('/')
    
    # Handle both ObjectId and email-based user_id (for demo users)
    user_id = session['user_id']
    try:
        from bson import ObjectId
        user_query = {'$or': [{'user_id': user_id}, {'user_id': ObjectId(user_id)}]}
    except Exception:
        user_query = {'user_id': user_id}
    
    if request.method == 'GET':
        # Render the pickup request form (preserve existing behavior)
        # Ensure we pass a list (not a Cursor) so templates can use length/iteration safely
        requests = list(mongo.db.pickup_requests.find(user_query).sort('created_at', -1))

        pipeline = [
            {'$match': user_query},
            {'$group': {'_id': None, 'total': {'$sum': {'$ifNull': ['$approx_weight', '$ewaste_weight']}}}}
        ]
        weight_res = list(mongo.db.pickup_requests.aggregate(pipeline))
        total_donated = weight_res[0]['total'] if weight_res else 0

        return render_template('user/request_pickup.html', requests=requests, total_donated=total_donated)

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
            'user_name': session.get('name', 'User'),
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
            'engineer_id': None,
            'inspection_images': [],
            'inspection_status': None,  # pending, accepted, rejected
            'created_at': datetime.utcnow()
        }

        result = mongo.db.pickup_requests.insert_one(data)
        pickup_id = result.inserted_id
        
        # ============ AUTO-CLUSTER FORMATION ============
        CLUSTER_RADIUS_KM = 15
        CLUSTER_MIN_WEIGHT = 100000  # 100kg in grams
        CLUSTER_MAX_WEIGHT = 1000000 # 1000kg in grams
        
        lat_pickup = float(lat) if lat else None
        lng_pickup = float(lng) if lng else None
        
        if lat_pickup and lng_pickup:
            nearby = list(mongo.db.pickup_requests.find({
                'status': {'$in': ['pending', 'clustered']},
                'cluster_id': {'$exists': False}
            }))
            
            def haversine_km(lat1, lon1, lat2, lon2):
                R = 6371
                d_lat = math.radians(lat2 - lat1)
                d_lon = math.radians(lon2 - lon1)
                a = (math.sin(d_lat/2)**2 + 
                     math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2)
                return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            cluster_users = [{
                'user_id': pickup_id,
                'weight': total_weight,
                'distance_km': 0
            }]
            total_cluster_weight = total_weight
            
            for p in nearby:
                if p['_id'] == pickup_id:
                    continue
                p_lat = p.get('latitude')
                p_lng = p.get('longitude')
                if not (p_lat and p_lng):
                    continue
                
                dist = haversine_km(lat_pickup, lng_pickup, p_lat, p_lng)
                p_weight = p.get('approx_weight', p.get('ewaste_weight', 0))
                
                if dist <= CLUSTER_RADIUS_KM and total_cluster_weight + p_weight <= CLUSTER_MAX_WEIGHT:
                    cluster_users.append({
                        'user_id': p['_id'],
                        'weight': p_weight,
                        'distance_km': round(dist, 2)
                    })
                    total_cluster_weight += p_weight
            
            if total_cluster_weight >= CLUSTER_MIN_WEIGHT:
                cluster_status = 'ready'
            elif total_cluster_weight >= CLUSTER_MIN_WEIGHT * 0.7:
                cluster_status = 'almost_ready'
            else:
                cluster_status = 'pending'
            
            WAREHOUSES = [
                {"name": "North Warehouse (Borivali)", "lat": 19.2300, "lng": 72.8567},
                {"name": "West Warehouse (Andheri)", "lat": 19.1136, "lng": 72.8697},
                {"name": "East Warehouse (Thane)", "lat": 19.2183, "lng": 72.9781},
                {"name": "South Warehouse (Colaba)", "lat": 18.9067, "lng": 72.8147},
                {"name": "CENTRAL HUB (Ghatkopar)", "lat": 19.0860, "lng": 72.9090}
            ]
            nearest_wh = min(WAREHOUSES, key=lambda wh: haversine_km(lat_pickup, lng_pickup, wh['lat'], wh['lng']))
            dist_to_hub = haversine_km(lat_pickup, lng_pickup, nearest_wh['lat'], nearest_wh['lng'])
            
            cluster_doc = {
                'anchor_user_id': pickup_id,
                'anchor_location': {'lat': lat_pickup, 'lng': lng_pickup},
                'destination': nearest_wh['name'],
                'dist_to_hub': round(dist_to_hub, 2),
                'users': cluster_users,
                'total_weight': total_cluster_weight,
                'user_count': len(cluster_users),
                'status': cluster_status,
                'created_at': datetime.utcnow(),
                'engineer_id': None,
                'driver_id': None,
                'doctor_id': None
            }
            
            cluster_result = mongo.db.collection_clusters.insert_one(cluster_doc)
            cluster_id = str(cluster_result.inserted_id)
            
            for u in cluster_users:
                mongo.db.pickup_requests.update_one(
                    {'_id': u['user_id']},
                    {'$set': {'cluster_id': cluster_id, 'status': 'clustered'}}
                )
            
            from routes.notification_routes import create_notification
            create_notification(
                recipient_id=str(session['user_id']),
                title='Request Received',
                message=f'Your e-waste request has been received and added to a collection route. Drop-off: {nearest_wh["name"]}',
                notification_type='request_clustered',
                related_data={'cluster_id': cluster_id, 'status': cluster_status}
            )
        
        flash('Pickup request submitted successfully', 'success')

    except ValueError:
        flash('Invalid weight provided', 'error')
    except Exception as e:
        print(f"Error in create_request: {e}")
        flash('Error submitting request', 'error')

    return redirect('/user/dashboard')
