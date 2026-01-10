from flask import Blueprint, render_template
from routes.auth_routes import login_required, role_required

engineer_bp = Blueprint('engineer', __name__)

@engineer_bp.route('/engineer/dashboard')
@login_required
@role_required('engineer')
def engineer_dashboard():
    return render_template('engineer/engineer_dashboard.html')
