from flask import Blueprint, render_template, request, redirect, url_for
from database.mongo import mongo
from bson import ObjectId
from datetime import datetime
import math

warehouse_bp = Blueprint("warehouse", __name__)

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

    # attach user details
    for cluster in clusters:
        users = []
        for u in cluster["users"]:
            req = mongo.db.pickup_requests.find_one({"_id": u["user_id"]})
            if req:
                users.append({
                    "name": req["user_name"],
                    "address": req["address"],
                    "weight": u["weight"],
                    "distance": u["distance_km"]
                })
        cluster["user_details"] = users

    return render_template(
        "warehouse/warehouse_dashboard.html",
        clusters=clusters
    )


# ---------------- ANALYZE ROUTES ENGINE ----------------
@warehouse_bp.route("/analyze-routes", methods=["POST"])
def analyze_routes():
    users = list(mongo.db.pickup_requests.find({
        "status": "pending",
        "cluster_id": None
    }))

    users.sort(key=lambda u: u["ewaste_weight"], reverse=True)

    used_users = set()
    created = []

    for anchor in users:
        if anchor["_id"] in used_users:
            continue

        cluster_users = [{
            "user_id": anchor["_id"],
            "weight": anchor["ewaste_weight"],
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
                cluster_users.append({
                    "user_id": u["_id"],
                    "weight": u["ewaste_weight"],
                    "distance_km": round(dist, 2)
                })
                total_weight += u["ewaste_weight"]
                max_distance = max(max_distance, dist)
                used_users.add(u["_id"])

            if total_weight >= 100:
                break

        if total_weight >= 100:
            status = "ready"
        elif total_weight >= 85:
            status = "almost_ready"
        else:
            status = "pending"

        cluster = {
            "anchor_user_id": anchor["_id"],
            "anchor_location": {
                "lat": anchor["latitude"],
                "lng": anchor["longitude"]
            },
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


# ---------------- ADMIN OVERRIDE ----------------
@warehouse_bp.route("/approve/<cluster_id>", methods=["POST"])
def approve_cluster(cluster_id):
    mongo.db.collection_clusters.update_one(
        {"_id": ObjectId(cluster_id), "status": "almost_ready"},
        {"$set": {"status": "ready", "admin_override": True}}
    )
    return redirect(url_for("warehouse.dashboard"))
