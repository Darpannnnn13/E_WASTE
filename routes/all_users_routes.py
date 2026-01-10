from flask import Blueprint, render_template, session
from routes.auth_routes import login_required

all_users_bp = Blueprint('all_users', __name__)

@all_users_bp.route('/all_users')
@login_required
def all_users_page():
    return render_template('all_users.html', user_role=session.get('role'))
