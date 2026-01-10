from pymongo import MongoClient
from datetime import datetime

# ---------------- CONFIG ----------------
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "ewaste_db"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# ---------------- CLEAN OLD DATA ----------------
db.pickup_requests.delete_many({})
db.collection_clusters.delete_many({})

print("Old data cleared")

# ---------------- SEED USERS ----------------
users = [
    {
        "user_name": "Rahul Sharma",
        "address": "Andheri East, Mumbai",
        "latitude": 19.1176,
        "longitude": 72.8631,
        "ewaste_weight": 60,
        "product_type": "Desktop PC",
        "status": "pending",
        "cluster_id": None,
        "created_at": datetime.utcnow()
    },
    {
        "user_name": "Amit Verma",
        "address": "Jogeshwari West, Mumbai",
        "latitude": 19.1360,
        "longitude": 72.8486,
        "ewaste_weight": 30,
        "product_type": "Laptop",
        "status": "pending",
        "cluster_id": None,
        "created_at": datetime.utcnow()
    },
    {
        "user_name": "Suresh Patil",
        "address": "Borivali East, Mumbai",
        "latitude": 19.2290,
        "longitude": 72.8567,
        "ewaste_weight": 25,
        "product_type": "Printer",
        "status": "pending",
        "cluster_id": None,
        "created_at": datetime.utcnow()
    },
    {
        "user_name": "Neha Joshi",
        "address": "Thane West",
        "latitude": 19.2183,
        "longitude": 72.9781,
        "ewaste_weight": 40,
        "product_type": "Office PCs",
        "status": "pending",
        "cluster_id": None,
        "created_at": datetime.utcnow()
    },
    {
        "user_name": "Karan Mehta",
        "address": "Kalyan",
        "latitude": 19.2403,
        "longitude": 73.1305,
        "ewaste_weight": 55,
        "product_type": "Server Racks",
        "status": "pending",
        "cluster_id": None,
        "created_at": datetime.utcnow()
    },
    {
        "user_name": "Priya Nair",
        "address": "Navi Mumbai",
        "latitude": 19.0330,
        "longitude": 73.0297,
        "ewaste_weight": 20,
        "product_type": "Mobile Devices",
        "status": "pending",
        "cluster_id": None,
        "created_at": datetime.utcnow()
    },
    {
        "user_name": "Vikas Singh",
        "address": "Panvel",
        "latitude": 18.9894,
        "longitude": 73.1175,
        "ewaste_weight": 35,
        "product_type": "UPS Batteries",
        "status": "pending",
        "cluster_id": None,
        "created_at": datetime.utcnow()
    }
]

# ---------------- INSERT DATA ----------------
db.pickup_requests.insert_many(users)

print(f"{len(users)} users inserted successfully")

# ---------------- VERIFY ----------------
print("\nSeeded Users:")
for u in db.pickup_requests.find():
    print(f"- {u['user_name']} | {u['ewaste_weight']} kg | {u['address']}")

print("\n✅ Database seeded successfully. You can now:")
print("1. Open /warehouse/dashboard")
print("2. Click 'Analyze Routes'")
print("3. See READY / ALMOST READY / PENDING clusters")