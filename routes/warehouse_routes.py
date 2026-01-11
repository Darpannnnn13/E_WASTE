from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from mongo import mongo
from bson import ObjectId
from datetime import datetime
from datetime import timedelta
import math

warehouse_bp = Blueprint("warehouse", __name__)

# ---------------- WAREHOUSE LOCATIONS ----------------
WAREHOUSES = [
    {"id": 1, "name": "North Warehouse (Borivali)", "lat": 19.2300, "lng": 72.8567},
    {"id": 2, "name": "West Warehouse (Andheri)", "lat": 19.1136, "lng": 72.8697},
    {"id": 3, "name": "East Warehouse (Thane)", "lat": 19.2183, "lng": 72.9781},
    {"id": 4, "name": "South Warehouse (Colaba)", "lat": 18.9067, "lng": 72.8147},
    {"id": 5, "name": "CENTRAL HUB (Ghatkopar)", "lat": 19.0860, "lng": 72.9090} # Central Collection Point
]

# ---------------- DISTANCE FUNCTION ----------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(d_lon / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------- DASHBOARD ----------------
@warehouse_bp.route("/dashboard")
def dashboard():
    clusters = list(mongo.db.collection_clusters.find().sort("created_at", -1))

    # ---------------- ANALYTICS & INSIGHTS ----------------
    # 1. KPI Cards Data
    total_requests = mongo.db.pickup_requests.count_documents({})
    pending_count = mongo.db.pickup_requests.count_documents({"status": "pending"})
    collected_count = mongo.db.pickup_requests.count_documents({"status": "collected"})
    recycled_count = mongo.db.pickup_requests.count_documents({"status": "recycled"})
    
    # Calculate Total Weight (handling both 'approx_weight' from form and 'ewaste_weight' from seed)
    pipeline_weight = [
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$approx_weight", "$ewaste_weight"]}}}}
    ]
    weight_res = list(mongo.db.pickup_requests.aggregate(pipeline_weight))
    total_weight = weight_res[0]['total'] if weight_res else 0

    # 2. Material Composition (Pie Chart)
    pipeline_type = [
        {"$group": {"_id": "$ewaste_type", "count": {"$sum": 1}}}
    ]
    type_data = list(mongo.db.pickup_requests.aggregate(pipeline_type))
    chart_labels = [d["_id"] for d in type_data if d["_id"]]
    chart_values = [d["count"] for d in type_data if d["_id"]]

    # 3. Predictive Forecast (Mock AI Model)
    # Simulating a 15% week-over-week growth prediction
    forecast_labels = ["Current Week", "Week +1", "Week +2", "Week +3"]
    forecast_values = [total_weight, total_weight * 1.15, total_weight * 1.32, total_weight * 1.52]

    # 4. Workforce Monitoring
    # Fetch engineers and check if they are currently on a job AND available tomorrow
    engineers = list(mongo.db.users.find({"role": "engineer"}))
    active_engineer_ids = mongo.db.collection_clusters.distinct("engineer_id", {"status": "in_progress"})
    
    for eng in engineers:
        eng['status'] = 'On Route' if str(eng['_id']) in active_engineer_ids else 'Available'
        eng['available_tomorrow'] = eng.get('available_tomorrow', True)  # Default to available
        
    drivers = list(mongo.db.users.find({"role": "driver"}))
    active_driver_ids = mongo.db.collection_clusters.distinct("driver_id", {"status": "in_progress"})
    
    for drv in drivers:
        drv['status'] = 'On Route' if str(drv['_id']) in active_driver_ids else 'Available'

    recyclers = list(mongo.db.users.find({"role": "recycler"}))

    # 5. Warehouse Inventory (Collected items waiting for recycling)
    inventory_items = list(mongo.db.pickup_requests.find({"status": "collected"}).sort("updated_at", -1).limit(10))

    # 6. Leaderboard
    leaderboard_pipeline = [
        {'$group': {'_id': '$user_name', 'total_weight': {'$sum': {'$ifNull': ['$approx_weight', '$ewaste_weight']}}}},
        {'$sort': {'total_weight': -1}},
        {'$limit': 5}
    ]
    leaderboard = list(mongo.db.pickup_requests.aggregate(leaderboard_pipeline))

    # attach user details and category/type info for each cluster
    for cluster in clusters:
        users = []
        categories = set()
        for u in cluster["users"]:
            req = mongo.db.pickup_requests.find_one({"_id": u["user_id"]})
            if req:
                users.append({
                    "name": req["user_name"],
                    "address": req["address"],
                    "weight": u["weight"],
                    "distance": u["distance_km"],
                    "type": req.get("ewaste_type", "Unknown")
                })
                # Collect all unique categories in this cluster
                if req.get("ewaste_type"):
                    categories.add(req.get("ewaste_type"))
        
        cluster["user_details"] = users
        cluster["categories"] = ", ".join(list(categories)) if categories else "Mixed E-Waste"
        
        # Fetch assigned engineer and driver names
        engineer_name = None
        driver_name = None
        if cluster.get("engineer_id"):
            try:
                eng_doc = mongo.db.users.find_one({"_id": ObjectId(cluster["engineer_id"])})
                engineer_name = eng_doc.get("name") if eng_doc else None
            except Exception:
                engineer_name = None
        if cluster.get("driver_id"):
            try:
                drv_doc = mongo.db.users.find_one({"_id": ObjectId(cluster["driver_id"])})
                driver_name = drv_doc.get("name") if drv_doc else None
            except Exception:
                driver_name = None
        
        cluster["engineer_name"] = engineer_name
        cluster["driver_name"] = driver_name
        
        # Ensure destination is set
        if not cluster.get("destination"):
            lat = cluster.get("anchor_location", {}).get("lat")
            lng = cluster.get("anchor_location", {}).get("lng")
            if lat and lng:
                nearest_wh = min(WAREHOUSES, key=lambda wh: haversine_km(lat, lng, wh["lat"], wh["lng"]))
                cluster["destination"] = nearest_wh["name"]
            else:
                cluster["destination"] = "Drop-off Hub"

    return render_template(
        "warehouse/warehouse_dashboard.html",
        clusters=clusters,
        stats={
            "total_requests": total_requests,
            "pending": pending_count,
            "collected": collected_count,
            "recycled": recycled_count,
            "total_weight": total_weight,
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "forecast_labels": forecast_labels,
            "forecast_values": forecast_values,
            "engineers": engineers,
            "drivers": drivers,
            "recyclers": recyclers,
            "inventory": inventory_items,
            "leaderboard": leaderboard
        },
        warehouses=WAREHOUSES
    )


# ---------------- ADVANCED ANALYTICS DASHBOARD ----------------
@warehouse_bp.route("/advanced-analytics")
def advanced_analytics():
    # Advanced metrics
    total_requests = mongo.db.pickup_requests.count_documents({})
    pending_count = mongo.db.pickup_requests.count_documents({"status": "pending"})
    collected_count = mongo.db.pickup_requests.count_documents({"status": "collected"})
    recycled_count = mongo.db.pickup_requests.count_documents({"status": "recycled"})
    
    # Calculate completion rate
    completion_rate = (collected_count / total_requests * 100) if total_requests > 0 else 0
    
    # Total weight
    pipeline_weight = [
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$approx_weight", "$ewaste_weight"]}}}}
    ]
    weight_res = list(mongo.db.pickup_requests.aggregate(pipeline_weight))
    total_weight = weight_res[0]['total'] if weight_res else 0
    
    # Material breakdown
    pipeline_material = [
        {"$group": {"_id": "$ewaste_type", "count": {"$sum": 1}, "total_weight": {"$sum": {"$ifNull": ["$approx_weight", "$ewaste_weight"]}}}}
    ]
    material_data = list(mongo.db.pickup_requests.aggregate(pipeline_material))
    
    # Engineer performance
    engineers = list(mongo.db.users.find({"role": "engineer"}))
    for eng in engineers:
        completed = mongo.db.pickup_requests.count_documents({"engineer_id": str(eng["_id"]), "status": "collected"})
        eng["jobs_completed"] = completed
        eng["available"] = eng.get("available_tomorrow", True)
    
    # Cluster efficiency
    clusters = list(mongo.db.collection_clusters.find().sort("created_at", -1).limit(10))
    
    # Recycler performance
    recycled_items = mongo.db.pickup_requests.count_documents({"status": "recycled"})
    recyclers = list(mongo.db.users.find({"role": "recycler"}))
    
    # Time-based analytics
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    
    pipeline_daily = [
        {"$match": {"created_at": {"$gte": datetime.combine(week_ago, datetime.min.time())}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "count": {"$sum": 1}}}
    ]
    daily_data = sorted(list(mongo.db.pickup_requests.aggregate(pipeline_daily)), key=lambda x: x["_id"])
    # Prepare a limited, reverse-chronological slice for template rendering to avoid Jinja async filter issues
    daily_data_limited = list(reversed(daily_data))[:7]

    return render_template(
        "warehouse/advanced_analytics.html",
        total_requests=total_requests,
        pending=pending_count,
        collected=collected_count,
        recycled=recycled_count,
        completion_rate=round(completion_rate, 2),
        total_weight=total_weight,
        material_data=material_data,
        engineers=engineers,
        clusters=clusters,
        recyclers=recyclers,
        recycled_items=recycled_items,
        daily_data=daily_data,
        daily_data_limited=daily_data_limited
    )


# ---------------- ANALYZE ROUTES ENGINE ----------------
@warehouse_bp.route("/analyze-routes", methods=["POST"])
def analyze_routes():
    users = list(mongo.db.pickup_requests.find({
        "status": "pending",
        "cluster_id": None
    }))

    # Filter out requests with missing coordinates to prevent KeyError
    users = [u for u in users if u.get('latitude') is not None and u.get('longitude') is not None]

    # Sort by weight (handle both field names for compatibility)
    users.sort(key=lambda u: u.get("approx_weight", u.get("ewaste_weight", 0)), reverse=True)

    used_users = set()
    created = []

    for anchor in users:
        if anchor["_id"] in used_users:
            continue
        
        # Find nearest Regional Warehouse (1-4) for drop-off
        nearest_wh = min(WAREHOUSES[:4], key=lambda wh: haversine_km(
            anchor["latitude"], anchor["longitude"], wh["lat"], wh["lng"]
        ))
        
        dist_to_wh = haversine_km(
            anchor["latitude"], anchor["longitude"],
            nearest_wh["lat"], nearest_wh["lng"]
        )
        
        anchor_weight = anchor.get("approx_weight", anchor.get("ewaste_weight", 0))

        cluster_users = [{
            "user_id": anchor["_id"],
            "weight": anchor_weight,
            "distance_km": 0
        }]
        total_weight = anchor["ewaste_weight"]
        max_distance = 0
        used_users.add(anchor["_id"])

        for u in users:
            if u["_id"] in used_users:
                continue

            dist = haversine_km(
                anchor["latitude"], anchor["longitude"],
                u["latitude"], u["longitude"]
            )

            if dist <= 100:
                u_weight = u.get("approx_weight", u.get("ewaste_weight", 0))
                cluster_users.append({
                    "user_id": u["_id"],
                    "weight": u_weight,
                    "distance_km": round(dist, 2)
                })
                
                total_weight += u_weight
                max_distance = max(max_distance, dist)
                used_users.add(u["_id"])

            if total_weight >= 100000: # 100kg limit for cluster
                break

        if total_weight >= 100000: # 100kg -> Ready
            status = "ready"
        elif total_weight >= 80000: # 80kg -> Almost Ready
            status = "almost_ready"
        else:
            status = "pending"

        cluster = {
            "anchor_user_id": anchor["_id"],
            "anchor_location": {
                "lat": anchor["latitude"],
                "lng": anchor["longitude"]
            },
            "destination": nearest_wh["name"],
            "dist_to_hub": round(dist_to_wh, 2), # Distance to drop-off point
            "radius_used_km": round(max_distance, 2),
            "total_weight": total_weight,
            "user_count": len(cluster_users),
            "users": cluster_users,
            "efficiency_score": round(total_weight / max_distance, 2) if max_distance else total_weight,
            "status": status,
            "admin_override": False,
            "created_at": datetime.utcnow()
        }

        cid = mongo.db.collection_clusters.insert_one(cluster).inserted_id

        mongo.db.pickup_requests.update_many(
            {"_id": {"$in": [u["user_id"] for u in cluster_users]}},
            {"$set": {"status": "clustered", "cluster_id": cid}}
        )

        created.append(str(cid))

    return redirect(url_for("warehouse.dashboard"))


@warehouse_bp.route('/assign/<cluster_id>', methods=['GET'])
def assign_cluster_page(cluster_id):
    # Render a simple assignment page for a cluster
    cluster = mongo.db.collection_clusters.find_one({'_id': ObjectId(cluster_id)})
    if not cluster:
        return redirect(url_for('warehouse.dashboard'))

    # Fetch available engineers/drivers/doctors
    engineers = list(mongo.db.users.find({'role': 'engineer'}))
    drivers = list(mongo.db.users.find({'role': 'driver'}))
    doctors = list(mongo.db.users.find({'role': 'doctor'}))

    # Determine cluster centroid (anchor or centroid of users)
    lat = None
    lng = None
    if cluster.get('anchor_location'):
        lat = cluster['anchor_location'].get('lat')
        lng = cluster['anchor_location'].get('lng')
    else:
        user_ids = [u['user_id'] for u in cluster.get('users', [])]
        if user_ids:
            pickup_docs = list(mongo.db.pickup_requests.find({'_id': {'$in': user_ids}}))
            if pickup_docs:
                lat = sum([p.get('latitude', 0) for p in pickup_docs]) / len(pickup_docs)
                lng = sum([p.get('longitude', 0) for p in pickup_docs]) / len(pickup_docs)

    # Only show engineers who are available_tomorrow or currently not on route
    active_engineer_ids = mongo.db.collection_clusters.distinct('engineer_id', {'status': {'$in': ['in_progress', 'assigned', 'scheduled']}})
    for eng in engineers:
        eng['on_route'] = str(eng['_id']) in active_engineer_ids
        eng['available_tomorrow'] = eng.get('available_tomorrow', True)
        # compute current active assignment count for workload-based recommendation
        try:
            eng_count = mongo.db.collection_clusters.count_documents({'engineer_id': str(eng['_id']), 'status': {'$in': ['assigned', 'in_progress', 'scheduled']}})
        except Exception:
            eng_count = 0
        eng['active_count'] = eng_count

    for drv in drivers:
        try:
            drv_count = mongo.db.collection_clusters.count_documents({'driver_id': str(drv['_id']), 'status': {'$in': ['assigned', 'in_progress', 'scheduled']}})
        except Exception:
            drv_count = 0
        drv['active_count'] = drv_count

    # Sort by availability then by active_count (less loaded first)
    engineers_sorted = sorted(engineers, key=lambda p: (0 if p.get('available_tomorrow', True) else 1, p.get('active_count', 0)))
    drivers_sorted = sorted(drivers, key=lambda p: (0 if p.get('available_tomorrow', True) else 1, p.get('active_count', 0)))

    # Prepare recommended (top 5)
    recommended_engineers = engineers_sorted[:5]
    recommended_drivers = drivers_sorted[:5]

    recommended_engineer_id = str(recommended_engineers[0]['_id']) if recommended_engineers else None
    recommended_driver_id = str(recommended_drivers[0]['_id']) if recommended_drivers else None

    return render_template(
        'warehouse/assign_cluster.html',
        cluster=cluster,
        engineers=engineers_sorted,
        drivers=drivers_sorted,
        doctors=doctors,
        recommended_engineers=recommended_engineers,
        recommended_drivers=recommended_drivers,
        recommended_engineer_id=recommended_engineer_id,
        recommended_driver_id=recommended_driver_id
    )

@warehouse_bp.route('/assign', methods=['POST'])
def assign_cluster():
    cluster_id = request.form.get('cluster_id')
    eng_id = request.form.get('engineer_id')
    driver_id = request.form.get('driver_id')
    doctor_id = request.form.get('doctor_id')
    est_minutes = int(request.form.get('estimated_duration_minutes') or 60)
    route_km = float(request.form.get('route_distance_km') or 5.0)
    scheduled_for = datetime.utcnow()

    update = {
        'engineer_id': eng_id,
        'driver_id': driver_id,
        'doctor_id': doctor_id,
        'status': 'scheduled',
        'scheduled_for': scheduled_for,
        'estimated_duration_minutes': est_minutes,
        'route_distance_km': route_km
    }

    # compute and set destination if not present
    cluster = mongo.db.collection_clusters.find_one({'_id': ObjectId(cluster_id)})
    lat = None
    lng = None
    if cluster:
        if cluster.get('anchor_location'):
            lat = cluster['anchor_location'].get('lat')
            lng = cluster['anchor_location'].get('lng')
        else:
            user_ids = [u['user_id'] for u in cluster.get('users', [])]
            if user_ids:
                pickup_docs = list(mongo.db.pickup_requests.find({'_id': {'$in': user_ids}}))
                if pickup_docs:
                    lat = sum([p.get('latitude', 0) for p in pickup_docs]) / len(pickup_docs)
                    lng = sum([p.get('longitude', 0) for p in pickup_docs]) / len(pickup_docs)

    if lat is not None and lng is not None:
        nearest_wh = min(WAREHOUSES, key=lambda wh: haversine_km(lat, lng, wh['lat'], wh['lng']))
        dist_to_wh = round(haversine_km(lat, lng, nearest_wh['lat'], nearest_wh['lng']), 2)
        update['destination'] = nearest_wh['name']
        update['dist_to_hub'] = dist_to_wh

    mongo.db.collection_clusters.update_one({'_id': ObjectId(cluster_id)}, {'$set': update})

    # Update pickup_requests linked to this cluster: set status scheduled
    try:
        mongo.db.pickup_requests.update_many({'cluster_id': str(cluster_id)}, {'$set': {'status': 'scheduled'}})
    except Exception:
        pass

    return redirect(url_for('warehouse.dashboard'))


# ---------------- ADMIN OVERRIDE ----------------
@warehouse_bp.route("/approve/<cluster_id>", methods=["POST"])
def approve_cluster(cluster_id):
    mongo.db.collection_clusters.update_one(
        {"_id": ObjectId(cluster_id), "status": "almost_ready"},
        {"$set": {"status": "ready", "admin_override": True}}
    )
    return redirect(url_for("warehouse.dashboard"))


# ---------------- ASSIGN FLEET (ENGINEER + DRIVER) ----------------
@warehouse_bp.route("/assign/<cluster_id>", methods=["POST"])
def assign_fleet(cluster_id):
    engineer_id = request.form.get("engineer_id")
    driver_id = request.form.get("driver_id") # New field
    destination_hub = request.form.get("destination_hub")  # User-selected hub

    if engineer_id and driver_id and destination_hub:
        # Use selected hub as destination (no need to compute nearest)
        cluster = mongo.db.collection_clusters.find_one({"_id": ObjectId(cluster_id)})
        
        # Find the selected warehouse to get coordinates for distance calculation
        selected_warehouse = next((wh for wh in WAREHOUSES if wh['name'] == destination_hub), None)
        dist_to_wh = None
        
        if selected_warehouse and cluster:
            lat = None
            lng = None
            if cluster.get('anchor_location'):
                lat = cluster['anchor_location'].get('lat')
                lng = cluster['anchor_location'].get('lng')
            else:
                # compute centroid of users
                user_ids = [u['user_id'] for u in cluster.get('users', [])]
                if user_ids:
                    pickup_docs = list(mongo.db.pickup_requests.find({'_id': {'$in': user_ids}}))
                    if pickup_docs:
                        lat = sum([p.get('latitude', 0) for p in pickup_docs]) / len(pickup_docs)
                        lng = sum([p.get('longitude', 0) for p in pickup_docs]) / len(pickup_docs)
            
            if lat is not None and lng is not None:
                dist_to_wh = round(haversine_km(lat, lng, selected_warehouse['lat'], selected_warehouse['lng']), 2)

        mongo.db.collection_clusters.update_one(
            {"_id": ObjectId(cluster_id)},
            {"$set": {
                "status": "assigned",
                "engineer_id": engineer_id,
                "driver_id": driver_id,
                "assigned_at": datetime.utcnow(),
                "destination": destination_hub,
                "dist_to_hub": dist_to_wh,
                "scheduled_for": datetime.utcnow() if not (cluster and cluster.get('scheduled_for')) else cluster.get('scheduled_for')
            }}
        )

        # Update linked pickup_requests to assigned
        try:
            mongo.db.pickup_requests.update_many({'cluster_id': str(cluster_id)}, {'$set': {'status': 'assigned'}})
        except Exception:
            pass
    
    return redirect(url_for("warehouse.dashboard"))


# --------------- STATUS TRANSITIONS ---------------
@warehouse_bp.route("/update-cluster-status/<cluster_id>", methods=["POST"])
def update_cluster_status(cluster_id):
    """
    Update cluster status with notifications to all stakeholders.
    Transitions: assigned → out_for_delivery → delivered
    """
    from routes.notification_routes import create_notification
    
    new_status = request.json.get("status")
    cluster = mongo.db.collection_clusters.find_one({"_id": ObjectId(cluster_id)})
    
    if not cluster:
        return {"error": "Cluster not found"}, 404
    
    # Update cluster status and add to status history
    mongo.db.collection_clusters.update_one(
        {"_id": ObjectId(cluster_id)},
        {
            "$set": {"status": new_status, "updated_at": datetime.utcnow()},
            "$push": {
                "status_history": {
                    "status": new_status,
                    "timestamp": datetime.utcnow(),
                    "changed_by": "warehouse"
                }
            }
        }
    )
    
    # Notify all users in the cluster about status change
    if cluster.get("users"):
        status_msg = {
            "assigned": "Your e-waste collection has been assigned to our team",
            "out_for_delivery": "Our driver is on the way to collect your e-waste",
            "delivered": "Your e-waste has been delivered to our warehouse"
        }
        
        message = status_msg.get(new_status, f"Status updated to {new_status}")
        emoji = {
            "assigned": "📋",
            "out_for_delivery": "🚗",
            "delivered": "✓"
        }
        
        for user_info in cluster["users"]:
            try:
                create_notification(
                    recipient_id=user_info["user_id"],
                    title=f"{emoji.get(new_status, '●')} Collection {new_status.replace('_', ' ').title()}",
                    message=message,
                    type="status_update",
                    related_data={"cluster_id": str(cluster_id), "status": new_status}
                )
            except:
                pass
    
    # Notify engineer and driver
    if cluster.get("engineer_id"):
        try:
            create_notification(
                recipient_id=cluster["engineer_id"],
                title="Cluster Status Update",
                message=f"Cluster status changed to {new_status.replace('_', ' ')}",
                type="status_update",
                related_data={"cluster_id": str(cluster_id)}
            )
        except:
            pass
    
    if cluster.get("driver_id"):
        try:
            create_notification(
                recipient_id=cluster["driver_id"],
                title="Cluster Status Update",
                message=f"Cluster status changed to {new_status.replace('_', ' ')}",
                type="status_update",
                related_data={"cluster_id": str(cluster_id)}
            )
        except:
            pass
    
    return {"success": True, "status": new_status}, 200


# --------------- ROUTE VIEW ---------------
@warehouse_bp.route('/route/<cluster_id>')
def view_route(cluster_id):
    cluster = mongo.db.collection_clusters.find_one({'_id': ObjectId(cluster_id)})
    if not cluster:
        return redirect(url_for('warehouse.dashboard'))
    
    # Get all user pickups in the cluster
    u_ids = [u['user_id'] for u in cluster.get('users', [])]
    pickup_docs = []
    if u_ids:
        pickup_docs = list(mongo.db.pickup_requests.find({'_id': {'$in': u_ids}}))
    
    waypoints = []
    for pickup in pickup_docs:
        waypoints.append({
            'lat': pickup.get('latitude', 19.076),
            'lng': pickup.get('longitude', 72.877),
            'address': pickup.get('address', 'Unknown Location')
        })
    
    driver_id = cluster.get('driver_id')
    return render_template('engineer/route.html', waypoints=waypoints, driver_id=driver_id, view_only=True)


@warehouse_bp.route('/track-order/<pickup_id>')
def track_order(pickup_id):
    """Allow users to track the driver for their specific pickup"""
    pickup = mongo.db.pickup_requests.find_one({'_id': ObjectId(pickup_id)})
    if not pickup:
        return "Order not found", 404
    
    cluster_id = pickup.get('cluster_id')
    if not cluster_id:
        return render_template('engineer/route.html', waypoints=[], error="Not assigned to a route yet")
        
    return view_route(cluster_id)


@warehouse_bp.route('/api/public/driver-location/<driver_id>')
def public_driver_location(driver_id):
    """Public API for frontend polling of driver location"""
    location = mongo.db.driver_locations.find_one({'driver_id': driver_id})
    if location:
        return jsonify({
            'lat': location.get('lat'),
            'lng': location.get('lng'),
            'timestamp': location.get('timestamp')
        })
    return jsonify({}), 404


# --------------- HUB INVENTORY ---------------
@warehouse_bp.route("/hub-inventory/<hub_name>", methods=["GET"])
def hub_inventory(hub_name):
    """
    Fetch all pickups delivered to a specific warehouse hub
    """
    # Find all clusters with this destination hub that are delivered
    clusters = list(mongo.db.collection_clusters.find(
        {"destination": hub_name, "status": {"$in": ["delivered", "completed"]}}
    ))
    
    hub_pickups = []
    total_weight = 0
    total_value = 0
    category_breakdown = {}
    
    for cluster in clusters:
        # Get all pickups in this cluster
        pickups = list(mongo.db.pickup_requests.find({
            "cluster_id": str(cluster["_id"])
        }))
        
        for pickup in pickups:
            category = pickup.get("ewaste_type", "Unknown")
            category_breakdown[category] = category_breakdown.get(category, 0) + 1
            
            # Calculate estimated value
            estimated_value = 0
            if pickup.get("final_weight"):
                # Check pricing engine for metal/category prices
                weight = pickup.get("final_weight", 0)
                metal_type = pickup.get("metal_type", "")
                
                if metal_type and mongo.db.metal_prices.find_one({"metal": metal_type}):
                    price_doc = mongo.db.metal_prices.find_one({"metal": metal_type})
                    estimated_value = weight * price_doc.get("price_per_kg", 0)
                else:
                    # Fallback to category pricing
                    category_price = mongo.db.category_prices.find_one({"category": category})
                    if category_price:
                        estimated_value = weight * category_price.get("price_per_kg", 0)
            
            total_weight += pickup.get("final_weight", pickup.get("approx_weight", pickup.get("ewaste_weight", 0)))
            total_value += estimated_value
            
            hub_pickups.append({
                "_id": str(pickup["_id"]),
                "user_name": pickup.get("user_name", "Unknown"),
                "ewaste_type": category,
                "status": pickup.get("status", "pending"),
                "final_weight": pickup.get("final_weight"),
                "approx_weight": pickup.get("approx_weight"),
                "final_quality": pickup.get("final_quality"),
                "collected_at": pickup.get("collected_at"),
                "items": pickup.get("items", []),
                "metal_type": pickup.get("metal_type"),
                "estimated_value": round(estimated_value, 2),
                "address": pickup.get("address"),
                "area": pickup.get("area")
            })
    
    return {
        "hub": hub_name,
        "total_pickups": len(hub_pickups),
        "total_weight": round(total_weight, 2),
        "total_estimated_value": round(total_value, 2),
        "category_breakdown": category_breakdown,
        "pickups": hub_pickups
    }, 200
