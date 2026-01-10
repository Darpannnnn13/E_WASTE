
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, abort
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from pymongo import MongoClient
import os

# Blueprint setup
auth_bp = Blueprint('auth', __name__)

# Registration route
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    success = None
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        address = request.form.get('address')
        age = request.form.get('age')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        users = get_users_collection()
        # Validation
        if not all([name, email, mobile, address, age, password, confirm_password]):
            error = 'All fields are required.'
        elif users.find_one({'email': email}):
            error = 'Email already registered.'
        elif users.find_one({'mobile': mobile}):
            error = 'Mobile number already registered.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        elif not mobile.isdigit() or len(mobile) != 10:
            error = 'Mobile number must be 10 digits.'
        elif not age.isdigit() or not (1 <= int(age) <= 120):
            error = 'Enter a valid age.'
        else:
            hashed_pw = generate_password_hash(password)
            users.insert_one({
                'name': name,
                'email': email,
                'mobile': mobile,
                'address': address,
                'age': int(age),
                'password': hashed_pw,
                'role': 'user'
            })
            success = 'Account created! You can now log in.'
            return render_template('register.html', success=success)
    return render_template('register.html', error=error)

# MongoDB connection helper
def get_users_collection():
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/e_waste')
    client = MongoClient(mongo_uri)
    db = client.get_default_database()
    return db['users']

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] != role:
                flash('Unauthorized access.', 'error')
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Login route
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        users = get_users_collection()
        user = users.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = user['role']
            return redirect(url_for('auth.role_redirect'))
        else:
            error = 'Invalid email or password.'
    return render_template('login.html', error=error)

# Role-based redirect
@auth_bp.route('/redirect')
def role_redirect():
    role = session.get('role')
    if role == 'user':
        return redirect('/user/request')
    elif role == 'engineer':
        return redirect('/engineer/dashboard')
    elif role == 'warehouse':
        return redirect('/warehouse/dashboard')
    else:
        return redirect(url_for('auth.login'))

# Logout route
@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

# Error handler for 403
@auth_bp.app_errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403
