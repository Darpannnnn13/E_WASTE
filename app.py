
from flask import Flask, render_template, session, redirect, url_for
from flask_pymongo import PyMongo
from routes.auth_routes import auth_bp
from routes.status_routes import status_bp
from routes.all_users_routes import all_users_bp
from routes.user_routes import user_bp
from routes.engineer_routes import engineer_bp
from routes.warehouse_routes import warehouse_bp
import os
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'devsecretkey')
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/e_waste')
mongo = PyMongo(app)
app.mongo = mongo  # Attach mongo to app for status route


# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(status_bp)
app.register_blueprint(all_users_bp)
app.register_blueprint(user_bp)
app.register_blueprint(engineer_bp)
app.register_blueprint(warehouse_bp)

# Example protected route (for testing)
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('auth.role_redirect'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True)
