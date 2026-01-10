from flask import Flask, session, redirect, render_template, request, url_for
from dotenv import load_dotenv
import os

# Mongo setup
from database.mongo import mongo

# Blueprints
from routes.user_routes import user_bp
from routes.auth_routes import auth_bp
#from routes.pricing_routes import pricing_bp
from routes.warehouse_routes import warehouse_bp
from routes.engineer_routes import engineer_bp
from routes.all_users_routes import all_users_bp
from routes.status_routes import status_bp

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/ewaste_db")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_secret")

    # Initialize MongoDB
    mongo.init_app(app)

    # Register Blueprints
    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)
    #app.register_blueprint(pricing_bp)
    app.register_blueprint(warehouse_bp, url_prefix="/warehouse")
    app.register_blueprint(engineer_bp)
    app.register_blueprint(all_users_bp)
    app.register_blueprint(status_bp)

    # Landing Route
    @app.route('/')
    def index():
        if 'user_id' in session:
            if session.get('role') == 'warehouse':
                return redirect(url_for('warehouse.dashboard'))
            elif session.get('role') == 'engineer':
                return redirect(url_for('engineer.engineer_dashboard'))
        return render_template('login.html')

    @app.route('/login', methods=['POST'])
    def login():
        email = request.form.get('email')
        # password = request.form.get('password') # In real app, verify password

        # Simple role detection for demo purposes
        role = 'user'
        if 'warehouse' in email:
            role = 'warehouse'
        elif 'engineer' in email:
            role = 'engineer'
        elif 'admin' in email:
            role = 'admin'

        session['user_id'] = email
        session['role'] = role
        
        return redirect('/')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect('/')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
