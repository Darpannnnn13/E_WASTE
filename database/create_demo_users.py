# Demo user creation script for MongoDB
from werkzeug.security import generate_password_hash
from pymongo import MongoClient
import os

mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/e_waste')
client = MongoClient(mongo_uri)
db = client.get_default_database()
users = db['users']

def create_demo_user(name, email, mobile, address, age, password, role):
    if not users.find_one({'email': email}):
        users.insert_one({
            'name': name,
            'email': email,
            'mobile': mobile,
            'address': address,
            'age': age,
            'password': generate_password_hash(password),
            'role': role
        })

# Demo users
demo_users = [
    ('Demo User', 'user@example.com', '9999999991', 'User Address', 25, 'userpass', 'user'),
    ('Demo Admin', 'admin@example.com', '9999999992', 'Admin Address', 30, 'adminpass', 'admin'),
    ('Demo Engineer', 'engineer@example.com', '9999999993', 'Engineer Address', 28, 'engineerpass', 'engineer'),
    ('Demo Warehouse', 'warehouse@example.com', '9999999994', 'Warehouse Address', 35, 'warehousepass', 'warehouse'),
]

for u in demo_users:
    create_demo_user(*u)

print('Demo users created.')
