from flask import Blueprint, render_template
from routes.auth_routes import login_required, role_required

user_bp = Blueprint('user', __name__)

@user_bp.route('/user/request')
@login_required
@role_required('user')
def user_request():
    return render_template('user/request_pickup.html')
