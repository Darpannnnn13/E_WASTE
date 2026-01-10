# seed.py: Seed MongoDB with demo users for E-Waste project
from werkzeug.security import generate_password_hash
from pymongo import MongoClient
import os

# MongoDB connection
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/e_waste')
client = MongoClient(mongo_uri)
db = client.get_default_database()
users = db['users']

# Remove all existing users (optional, for a clean seed)
users.delete_many({})

# Demo users to insert
seed_users = [
    {
        'name': 'Demo User',
        'email': 'user@example.com',
        'mobile': '9999999991',
        'address': 'User Address',
        'age': 25,
        'password': generate_password_hash('userpass'),
        'role': 'user'
    },
    {
        'name': 'Demo Admin',
        'email': 'admin@example.com',
        'mobile': '9999999992',
        'address': 'Admin Address',
        'age': 30,
        'password': generate_password_hash('adminpass'),
        'role': 'admin'
    },
    {
        'name': 'Demo Engineer',
        'email': 'engineer@example.com',
        'mobile': '9999999993',
        'address': 'Engineer Address',
        'age': 28,
        'password': generate_password_hash('engineerpass'),
        'role': 'engineer'
    },
    {
        'name': 'Demo Warehouse',
        'email': 'warehouse@example.com',
        'mobile': '9999999994',
        'address': 'Warehouse Address',
        'age': 35,
        'password': generate_password_hash('warehousepass'),
        'role': 'warehouse'
    }
]

# Insert demo users
users.insert_many(seed_users)

print('Database seeded with demo users.')
