from flask import Blueprint, render_template
from routes.auth_routes import login_required, role_required

warehouse_bp = Blueprint('warehouse', __name__)

@warehouse_bp.route('/warehouse/dashboard')
@login_required
@role_required('warehouse')
def warehouse_dashboard():
    return render_template('warehouse/warehouse_dashboard.html')
