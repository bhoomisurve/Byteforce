from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import sqlite3
import json
from functools import wraps
import logging

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///healthcare.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/prescriptions'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_type' not in session or session['user_type'] not in roles:
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Database helper functions
def get_db_connection():
    conn = sqlite3.connect('healthcare.db')
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=None):
    conn = get_db_connection()
    try:
        if params:
            result = conn.execute(query, params).fetchall()
        else:
            result = conn.execute(query).fetchall()
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Database error: {e}")
        return None
    finally:
        conn.close()

def execute_insert(query, params):
    conn = get_db_connection()
    try:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Database insert error: {e}")
        return None
    finally:
        conn.close()

# Routes

@app.route('/')
def index():
    """Landing page with platform overview"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for all user types"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = execute_query(
            'SELECT * FROM users WHERE email = ? AND is_active = TRUE',
            (email,)
        )
        
        if user and check_password_hash(user[0]['password_hash'], password):
            session['user_id'] = user[0]['id']
            session['user_type'] = user[0]['user_type']
            session['full_name'] = user[0]['full_name']
            
            flash(f'Welcome back, {user[0]["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')
from datetime import datetime

@app.template_filter('datefmt')
def datefmt(value, format="%Y-%m-%d"):
    if not value:
        return ''
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value  # return original string if parsing fails
    return value.strftime(format)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page for patients and pharmacies"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        
        # Check if user already exists
        existing_user = execute_query(
            'SELECT id FROM users WHERE email = ? OR username = ?',
            (email, username)
        )
        
        if existing_user:
            flash('User with this email or username already exists', 'error')
        else:
            password_hash = generate_password_hash(password)
            user_id = execute_insert(
                '''INSERT INTO users (username, email, password_hash, user_type, full_name, phone)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (username, email, password_hash, user_type, full_name, phone)
            )
            
            if user_id:
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Registration failed. Please try again.', 'error')
    
    # Get locations for dropdown
    locations = execute_query('SELECT * FROM locations ORDER BY name')
    return render_template('register.html', locations=locations)

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard - redirects to appropriate user dashboard"""
    user_type = session.get('user_type')
    
    if user_type == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif user_type == 'pharmacy':
        return redirect(url_for('pharmacy_dashboard'))
    elif user_type == 'patient':
        return redirect(url_for('patient_dashboard'))
    elif user_type in ['government', 'ngo']:
        return redirect(url_for('authority_dashboard'))
    else:
        flash('Unknown user type', 'error')
        return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
@role_required(['admin'])
def admin_dashboard():
    """Admin dashboard with system overview"""
    # Get system statistics
    stats = {
        'total_users': execute_query('SELECT COUNT(*) as count FROM users')[0]['count'],
        'total_pharmacies': execute_query('SELECT COUNT(*) as count FROM pharmacies')[0]['count'],
        'total_medicines': execute_query('SELECT COUNT(*) as count FROM medicines')[0]['count'],
        'active_alerts': execute_query('SELECT COUNT(*) as count FROM shortage_alerts WHERE is_active = TRUE')[0]['count'],
        'total_reports': execute_query('SELECT COUNT(*) as count FROM patient_reports')[0]['count']
    }
    
    # Get recent alerts
    recent_alerts = execute_query('''
        SELECT sa.*, m.name as medicine_name, l.name as location_name
        FROM shortage_alerts sa
        JOIN medicines m ON sa.medicine_id = m.id
        JOIN locations l ON sa.location_id = l.id
        WHERE sa.is_active = TRUE
        ORDER BY sa.created_at DESC LIMIT 10
    ''')
    
    # Get recent reports
    recent_reports = execute_query('''
        SELECT pr.*, m.name as medicine_name, l.name as location_name, u.full_name as reporter_name
        FROM patient_reports pr
        JOIN medicines m ON pr.medicine_id = m.id
        JOIN locations l ON pr.location_id = l.id
        LEFT JOIN users u ON pr.user_id = u.id
        ORDER BY pr.created_at DESC LIMIT 10
    ''')
    
    return render_template('admin_dashboard.html', 
                         stats=stats, 
                         recent_alerts=recent_alerts,
                         recent_reports=recent_reports)

@app.route('/pharmacy/dashboard')
@login_required
@role_required(['pharmacy'])
def pharmacy_dashboard():
    """Pharmacy dashboard for inventory management"""
    user_id = session.get('user_id')
    
    # Get pharmacy info
    pharmacy = execute_query(
        'SELECT * FROM pharmacies WHERE user_id = ?', 
        (user_id,)
    )[0] if execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,)) else None
    
    if not pharmacy:
        flash('Pharmacy profile not found. Please complete your profile.', 'warning')
        return redirect(url_for('profile'))
    
    # Get inventory with low stock alerts
    inventory = execute_query('''
        SELECT pi.*, m.name as medicine_name, m.generic_name, m.brand_name, m.dosage_form, m.strength
        FROM pharmacy_inventory pi
        JOIN medicines m ON pi.medicine_id = m.id
        WHERE pi.pharmacy_id = ?
        ORDER BY pi.current_stock ASC
    ''', (pharmacy['id'],))
    
    # Get low stock items
    low_stock = [item for item in inventory if item['current_stock'] <= item['minimum_stock_level']]
    
    return render_template('pharmacy_dashboard.html', 
                         pharmacy=pharmacy,
                         inventory=inventory,
                         low_stock=low_stock)

@app.route('/patient/dashboard')
@login_required
@role_required(['patient'])
def patient_dashboard():
    """Patient dashboard for reporting and viewing medicine availability"""
    user_id = session.get('user_id')
    
    # Get user's reports
    my_reports = execute_query('''
        SELECT pr.*, m.name as medicine_name, l.name as location_name, p.pharmacy_name
        FROM patient_reports pr
        JOIN medicines m ON pr.medicine_id = m.id
        JOIN locations l ON pr.location_id = l.id
        LEFT JOIN pharmacies p ON pr.pharmacy_id = p.id
        WHERE pr.user_id = ?
        ORDER BY pr.created_at DESC
    ''', (user_id,))
    
    # Get active alerts in user's area (assuming Mumbai for now)
    active_alerts = execute_query('''
        SELECT sa.*, m.name as medicine_name, l.name as location_name
        FROM shortage_alerts sa
        JOIN medicines m ON sa.medicine_id = m.id
        JOIN locations l ON sa.location_id = l.id
        WHERE sa.is_active = TRUE
        ORDER BY sa.severity DESC, sa.created_at DESC
        LIMIT 10
    ''')
    
    return render_template('patient_dashboard.html', 
                         my_reports=my_reports,
                         active_alerts=active_alerts)

@app.route('/authority/dashboard')
@login_required
@role_required(['government', 'ngo'])
def authority_dashboard():
    """Dashboard for government bodies and NGOs"""
    # Get critical alerts
    critical_alerts = execute_query('''
        SELECT sa.*, m.name as medicine_name, l.name as location_name
        FROM shortage_alerts sa
        JOIN medicines m ON sa.medicine_id = m.id
        JOIN locations l ON sa.location_id = l.id
        WHERE sa.is_active = TRUE AND sa.severity IN ('high', 'critical')
        ORDER BY sa.severity DESC, sa.created_at DESC
    ''')
    
    # Get shortage statistics by location
    shortage_stats = execute_query('''
        SELECT l.name as location_name, COUNT(*) as alert_count, 
               AVG(sa.price_increase_percentage) as avg_price_increase
        FROM shortage_alerts sa
        JOIN locations l ON sa.location_id = l.id
        WHERE sa.is_active = TRUE
        GROUP BY l.id, l.name
        ORDER BY alert_count DESC
    ''')
    
    return render_template('authority_dashboard.html', 
                         critical_alerts=critical_alerts,
                         shortage_stats=shortage_stats)

@app.route('/report-medicine', methods=['GET', 'POST'])
@login_required
@role_required(['patient'])
def report_medicine():
    """Page for patients to report medicine issues"""
    if request.method == 'POST':
        medicine_id = request.form.get('medicine_id')
        location_id = request.form.get('location_id')
        report_type = request.form.get('report_type')
        pharmacy_id = request.form.get('pharmacy_id') or None
        reported_price = request.form.get('reported_price')
        expected_price = request.form.get('expected_price')
        description = request.form.get('description')
        
        # Handle prescription upload
        prescription_file = request.files.get('prescription')
        prescription_filename = None
        if prescription_file and prescription_file.filename:
            prescription_filename = secure_filename(prescription_file.filename)
            prescription_file.save(os.path.join(app.config['UPLOAD_FOLDER'], prescription_filename))
        
        report_id = execute_insert('''
            INSERT INTO patient_reports (user_id, medicine_id, location_id, report_type, 
                                       pharmacy_id, reported_price, expected_price, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], medicine_id, location_id, report_type, 
              pharmacy_id, reported_price, expected_price, description))
        
        if report_id:
            flash('Report submitted successfully!', 'success')
            # Check if this triggers an alert
            check_and_create_alerts(medicine_id, location_id)
            return redirect(url_for('patient_dashboard'))
        else:
            flash('Failed to submit report', 'error')
    
    # Get data for form
    medicines = execute_query('SELECT * FROM medicines ORDER BY name')
    locations = execute_query('SELECT * FROM locations ORDER BY name')
    pharmacies = execute_query('SELECT * FROM pharmacies ORDER BY pharmacy_name')
    
    return render_template('report_medicine.html', 
                         medicines=medicines, 
                         locations=locations,
                         pharmacies=pharmacies)

@app.route('/inventory/manage')
@login_required
@role_required(['pharmacy'])
def manage_inventory():
    """Inventory management page for pharmacies"""
    user_id = session.get('user_id')
    pharmacy = execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,))[0]
    
    # Get all medicines for adding to inventory
    medicines = execute_query('SELECT * FROM medicines ORDER BY name')
    
    # Get current inventory
    inventory = execute_query('''
        SELECT pi.*, m.name as medicine_name, m.generic_name, m.brand_name
        FROM pharmacy_inventory pi
        JOIN medicines m ON pi.medicine_id = m.id
        WHERE pi.pharmacy_id = ?
        ORDER BY m.name
    ''', (pharmacy['id'],))
    
    return render_template('manage_inventory.html', 
                         medicines=medicines, 
                         inventory=inventory,
                         pharmacy=pharmacy)

@app.route('/inventory/update', methods=['POST'])
@login_required
@role_required(['pharmacy'])
def update_inventory():
    """API endpoint to update pharmacy inventory"""
    user_id = session.get('user_id')
    pharmacy = execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,))[0]
    
    medicine_id = request.form.get('medicine_id')
    current_stock = request.form.get('current_stock')
    unit_price = request.form.get('unit_price')
    mrp = request.form.get('mrp')
    batch_number = request.form.get('batch_number')
    expiry_date = request.form.get('expiry_date')
    minimum_stock_level = request.form.get('minimum_stock_level')
    
    # Check if item exists in inventory
    existing = execute_query('''
        SELECT id FROM pharmacy_inventory 
        WHERE pharmacy_id = ? AND medicine_id = ? AND batch_number = ?
    ''', (pharmacy['id'], medicine_id, batch_number))
    
    if existing:
        # Update existing inventory
        execute_query('''
            UPDATE pharmacy_inventory 
            SET current_stock = ?, unit_price = ?, mrp = ?, expiry_date = ?, 
                minimum_stock_level = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (current_stock, unit_price, mrp, expiry_date, minimum_stock_level, existing[0]['id']))
    else:
        # Add new inventory item
        execute_insert('''
            INSERT INTO pharmacy_inventory (pharmacy_id, medicine_id, current_stock, unit_price, 
                                          mrp, batch_number, expiry_date, minimum_stock_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pharmacy['id'], medicine_id, current_stock, unit_price, mrp, 
              batch_number, expiry_date, minimum_stock_level))
    
    flash('Inventory updated successfully!', 'success')
    return redirect(url_for('manage_inventory'))

@app.route('/medicine-search')
def medicine_search():
    """Public page for searching medicine availability"""
    medicines = execute_query('SELECT * FROM medicines ORDER BY name')
    locations = execute_query('SELECT * FROM locations ORDER BY name')
    
    search_results = []
    debug_info = {}
    
    if request.args.get('medicine_id') and request.args.get('location_id'):
        medicine_id = request.args.get('medicine_id')
        location_id = request.args.get('location_id')
        
        # First, let's check what data we have
        debug_info['medicine_id'] = medicine_id
        debug_info['location_id'] = location_id
        
        # Check if there's any inventory for this medicine at all
        all_inventory = execute_query('''
            SELECT pi.*, p.pharmacy_name, p.location_id, l.name as location_name, m.name as medicine_name
            FROM pharmacy_inventory pi
            JOIN pharmacies p ON pi.pharmacy_id = p.id
            JOIN medicines m ON pi.medicine_id = m.id
            JOIN locations l ON p.location_id = l.id
            WHERE pi.medicine_id = ?
        ''', (medicine_id,))
        
        debug_info['total_inventory_for_medicine'] = len(all_inventory) if all_inventory else 0
        
        # Try the main search query
        search_results = execute_query('''
            SELECT p.pharmacy_name, p.address, p.phone, pi.current_stock, 
                   pi.unit_price, pi.mrp, pi.batch_number, pi.expiry_date,
                   m.name as medicine_name, m.strength, m.dosage_form,
                   l.name as location_name
            FROM pharmacy_inventory pi
            JOIN pharmacies p ON pi.pharmacy_id = p.id
            JOIN medicines m ON pi.medicine_id = m.id
            JOIN locations l ON p.location_id = l.id
            WHERE pi.medicine_id = ? AND p.location_id = ? AND pi.current_stock > 0
            ORDER BY pi.unit_price ASC
        ''', (medicine_id, location_id))
        
        # If no results, try without stock filter
        if not search_results:
            search_results = execute_query('''
                SELECT p.pharmacy_name, p.address, p.phone, pi.current_stock, 
                       pi.unit_price, pi.mrp, pi.batch_number, pi.expiry_date,
                       m.name as medicine_name, m.strength, m.dosage_form,
                       l.name as location_name
                FROM pharmacy_inventory pi
                JOIN pharmacies p ON pi.pharmacy_id = p.id
                JOIN medicines m ON pi.medicine_id = m.id
                JOIN locations l ON p.location_id = l.id
                WHERE pi.medicine_id = ? AND p.location_id = ?
                ORDER BY pi.unit_price ASC
            ''', (medicine_id, location_id))
            
            if search_results:
                debug_info['note'] = "Found results but with zero stock"
        
        # If still no results, search all locations
        if not search_results:
            search_results = execute_query('''
                SELECT p.pharmacy_name, p.address, p.phone, pi.current_stock, 
                       pi.unit_price, pi.mrp, pi.batch_number, pi.expiry_date,
                       m.name as medicine_name, m.strength, m.dosage_form,
                       l.name as location_name
                FROM pharmacy_inventory pi
                JOIN pharmacies p ON pi.pharmacy_id = p.id
                JOIN medicines m ON pi.medicine_id = m.id
                JOIN locations l ON p.location_id = l.id
                WHERE pi.medicine_id = ?
                ORDER BY pi.unit_price ASC
                LIMIT 10
            ''', (medicine_id,))
            
            if search_results:
                debug_info['note'] = "Found results in other locations"
    
    return render_template('medicine_search.html', 
                         medicines=medicines, 
                         locations=locations,
                         search_results=search_results,
                         debug_info=debug_info if app.debug else None)

# Alternative more robust search endpoint
@app.route('/api/search-medicine', methods=['POST'])
def api_search_medicine():
    """API endpoint for medicine search with better error handling"""
    data = request.get_json()
    medicine_id = data.get('medicine_id')
    location_id = data.get('location_id')
    
    if not medicine_id:
        return jsonify({'error': 'Medicine ID is required'}), 400
    
    # Base query without location filter
    base_query = '''
        SELECT p.pharmacy_name, p.address, p.phone, pi.current_stock, 
               pi.unit_price, pi.mrp, pi.batch_number, pi.expiry_date,
               m.name as medicine_name, m.strength, m.dosage_form,
               l.name as location_name, l.id as location_id
        FROM pharmacy_inventory pi
        JOIN pharmacies p ON pi.pharmacy_id = p.id
        JOIN medicines m ON pi.medicine_id = m.id
        JOIN locations l ON p.location_id = l.id
        WHERE pi.medicine_id = ? AND pi.current_stock > 0
    '''
    
    params = [medicine_id]
    
    # Add location filter if provided
    if location_id:
        base_query += ' AND p.location_id = ?'
        params.append(location_id)
    
    base_query += ' ORDER BY pi.unit_price ASC'
    
    results = execute_query(base_query, params)
    
    return jsonify({
        'results': [dict(row) for row in results] if results else [],
        'count': len(results) if results else 0
    })

# Debug route to check data
@app.route('/debug/medicine-data')
@login_required
@role_required(['admin'])
def debug_medicine_data():
    """Debug route to check medicine and pharmacy data"""
    medicines_count = execute_query('SELECT COUNT(*) as count FROM medicines')[0]['count']
    pharmacies_count = execute_query('SELECT COUNT(*) as count FROM pharmacies')[0]['count']
    inventory_count = execute_query('SELECT COUNT(*) as count FROM pharmacy_inventory')[0]['count']
    locations_count = execute_query('SELECT COUNT(*) as count FROM locations')[0]['count']
    
    # Sample data
    sample_medicines = execute_query('SELECT * FROM medicines LIMIT 5')
    sample_pharmacies = execute_query('SELECT * FROM pharmacies LIMIT 5')
    sample_inventory = execute_query('''
        SELECT pi.*, m.name as medicine_name, p.pharmacy_name
        FROM pharmacy_inventory pi
        JOIN medicines m ON pi.medicine_id = m.id
        JOIN pharmacies p ON pi.pharmacy_id = p.id
        LIMIT 10
    ''')
    
    return jsonify({
        'counts': {
            'medicines': medicines_count,
            'pharmacies': pharmacies_count,
            'inventory': inventory_count,
            'locations': locations_count
        },
        'samples': {
            'medicines': [dict(row) for row in sample_medicines],
            'pharmacies': [dict(row) for row in sample_pharmacies],
            'inventory': [dict(row) for row in sample_inventory]
        }
    })
@app.route('/alerts')
@login_required
def view_alerts():
    """View all active alerts"""
    alerts = execute_query('''
        SELECT sa.*, m.name as medicine_name, l.name as location_name
        FROM shortage_alerts sa
        JOIN medicines m ON sa.medicine_id = m.id
        JOIN locations l ON sa.location_id = l.id
        WHERE sa.is_active = TRUE
        ORDER BY sa.severity DESC, sa.created_at DESC
    ''')
    
    return render_template('alerts.html', alerts=alerts)

@app.route('/analytics')
@login_required
@role_required(['admin', 'government', 'ngo'])
def analytics():
    """Analytics dashboard with charts and trends"""
    # Get shortage trends
    shortage_trends = execute_query('''
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM shortage_alerts
        WHERE created_at >= DATE('now', '-30 days')
        GROUP BY DATE(created_at)
        ORDER BY date
    ''')
    
    # Get top medicines with shortages
    top_shortage_medicines = execute_query('''
        SELECT m.name, COUNT(*) as shortage_count
        FROM shortage_alerts sa
        JOIN medicines m ON sa.medicine_id = m.id
        WHERE sa.created_at >= DATE('now', '-30 days')
        GROUP BY m.id, m.name
        ORDER BY shortage_count DESC
        LIMIT 10
    ''')
    
    # Get location-wise shortage distribution
    location_shortages = execute_query('''
        SELECT l.name, COUNT(*) as shortage_count
        FROM shortage_alerts sa
        JOIN locations l ON sa.location_id = l.id
        WHERE sa.created_at >= DATE('now', '-30 days')
        GROUP BY l.id, l.name
        ORDER BY shortage_count DESC
    ''')
    
    return render_template('analytics.html', 
                         shortage_trends=shortage_trends,
                         top_shortage_medicines=top_shortage_medicines,
                         location_shortages=location_shortages)

@app.route('/chatbot')
@login_required
def chatbot():
    """Medicine inventory chatbot interface"""
    return render_template('chatbot.html')

@app.route('/api/chatbot', methods=['POST'])
@login_required
def chatbot_api():
    """Simple chatbot API for medicine queries"""
    user_message = request.json.get('message', '').lower()
    
    # Simple keyword-based responses
    if 'insulin' in user_message:
        # Get insulin availability
        insulin_data = execute_query('''
            SELECT p.pharmacy_name, p.phone, pi.current_stock, pi.unit_price
            FROM pharmacy_inventory pi
            JOIN pharmacies p ON pi.pharmacy_id = p.id
            JOIN medicines m ON pi.medicine_id = m.id
            WHERE m.name LIKE '%insulin%' AND pi.current_stock > 0
            ORDER BY pi.unit_price ASC
            LIMIT 5
        ''')
        
        if insulin_data:
            response = "Here are pharmacies with insulin available:\n\n"
            for pharmacy in insulin_data:
                response += f"• {pharmacy['pharmacy_name']}: {pharmacy['current_stock']} units at ₹{pharmacy['unit_price']}\n"
        else:
            response = "Sorry, insulin is currently out of stock in nearby pharmacies."
    
    elif 'shortage' in user_message:
        # Get current shortages
        shortages = execute_query('''
            SELECT m.name, sa.severity, l.name as location
            FROM shortage_alerts sa
            JOIN medicines m ON sa.medicine_id = m.id
            JOIN locations l ON sa.location_id = l.id
            WHERE sa.is_active = TRUE
            ORDER BY sa.severity DESC
            LIMIT 5
        ''')
        
        if shortages:
            response = "Current medicine shortages:\n\n"
            for shortage in shortages:
                response += f"• {shortage['name']} - {shortage['severity']} shortage in {shortage['location']}\n"
        else:
            response = "No major shortages reported currently."
    
    else:
        response = "I can help you with medicine availability and shortage information. Try asking about specific medicines or current shortages!"
    
    return jsonify({'response': response})

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    user_id = session.get('user_id')
    user = execute_query('SELECT * FROM users WHERE id = ?', (user_id,))[0]
    
    return render_template('profile.html', user=user)

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

# Helper functions
def check_and_create_alerts(medicine_id, location_id):
    """Check if conditions warrant creating a shortage alert"""
    # Count recent reports for this medicine in this location
    recent_reports = execute_query('''
        SELECT COUNT(*) as count
        FROM patient_reports
        WHERE medicine_id = ? AND location_id = ? 
        AND created_at >= DATE('now', '-7 days')
    ''', (medicine_id, location_id))
    
    if recent_reports[0]['count'] >= 3:  # Threshold for creating alert
        # Check if alert already exists
        existing_alert = execute_query('''
            SELECT id FROM shortage_alerts
            WHERE medicine_id = ? AND location_id = ? AND is_active = TRUE
        ''', (medicine_id, location_id))
        
        if not existing_alert:
            # Create new alert
            execute_insert('''
                INSERT INTO shortage_alerts (medicine_id, location_id, alert_type, severity, description)
                VALUES (?, ?, 'shortage', 'medium', 'Multiple shortage reports received')
            ''', (medicine_id, location_id))

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.route("/map")
def map_view():
    pharmacies = execute_query(
        "SELECT pharmacy_name, address, latitude, longitude FROM pharmacies"
    )
    pharmacies_list = [dict(row) for row in pharmacies]
    print("Pharmacies JSON:", pharmacies_list)  # Debug all rows
    return render_template("map.html", pharmacies=json.dumps(pharmacies_list))

if __name__ == '__main__':
    # Initialize database if it doesn't exist
    if not os.path.exists('healthcare.db'):
        print("Database not found. Please run the schema script first.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
