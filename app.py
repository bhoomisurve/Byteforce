from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from web3 import Web3
import os
import sqlite3
import json
from functools import wraps
import pandas as pd
import logging
import joblib
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from math import radians, cos, sin, sqrt, atan2

import re
import requests
from io import BytesIO
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///healthcare.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/prescriptions'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
# Initialize geolocator once
geolocator = Nominatim(user_agent="my_medicine_app", timeout=10)
try:
    # Load dataset
    df = pd.read_csv("Medicine_Details.csv")
    # Clean column names
    df.columns = df.columns.str.strip()
    
    # Extract dosage from composition
    def extract_dosage(comp):
        doses = re.findall(r'(\d+)\s?mg', str(comp), re.IGNORECASE)
        return sum(map(int, doses)) if doses else 0
    
    df["Dosage (mg)"] = df["Composition"].apply(extract_dosage)
    
    # Ensure required columns exist
    df["Type"] = df.get("Type", "Tablet")
    df["Manufacturer"] = df.get("Manufacturer", "Unknown")
    df["Image URL"] = df.get("Image URL", "")
    
    # TF-IDF on composition
    tfidf = TfidfVectorizer()
    vectors = tfidf.fit_transform(df['Composition'])
    
    print("✅ Medicine dataset loaded successfully!")
except Exception as e:
    print(f"❌ Error loading medicine dataset: {e}")
    df = None
    tfidf = None
    vectors = None

# Helper function to get similar medicines
def get_similar_medicines(med_name):
    """Get similar medicines based on composition"""
    if df is None or med_name not in df["Medicine Name"].values:
        return None, None
    
    idx = df[df["Medicine Name"] == med_name].index[0]
    cosine_sim = cosine_similarity(vectors[idx], vectors).flatten()
    similar_idx = cosine_sim.argsort()[::-1][1:6]  # Top 5 similar
    
    main_med = df.loc[idx].to_dict()
    similar_meds = []
    
    for i in similar_idx:
        med = df.loc[i].to_dict()
        # Calculate similarity percentage
        med['similarity'] = round(cosine_sim[i] * 100, 2)
        similar_meds.append(med)
    
    return main_med, similar_meds

# Load ML models once at startup
model_shortage = joblib.load('medicine_shortage_model.pkl')
model_price = joblib.load('medicine_price_spike_model.pkl')

# Region, medicine and season mappings
region_map = {'Mumbai': 0, 'Delhi': 1, 'Chennai': 2, 'Kolkata': 3, 'Banglore': 4}
medicine_map = {
    'Insulin': 0, 'Thyroxine': 1, 'Metformin': 2, 'Levothyroxine': 3, 'Paracetamol': 4,
    'Amoxicillin': 5, 'Aspirin': 6, 'Atorvastatin': 7, 'Omeprazole': 8, 'Amlodipine': 9,
    'Azithromycin': 10, 'Cetrizine': 11, 'Doxycycline': 12, 'Diclofenac': 13, 'Losartan': 14,
    'Salbutamol': 15, 'Clopidogrel': 16, 'Fluconazole': 17, 'Levocetirizine': 18, 'Metronidazole': 19,
    'Montelukast': 20, 'Ciprofloxacin': 21, 'Prednisolone': 22, 'Ranitidine': 23, 'Warfarin': 24,
    'Glimepiride': 25, 'Levamisole': 26, 'Betahistine': 27, 'Norfloxacin': 28, 'Famotidine': 29,
    'Hydrochlorothiazide': 30, 'Tramadol': 31, 'Cefixime': 32, 'Clindamycin': 33, 'Olmesartan': 34,
    'Methylprednisolone': 35, 'Tiotropium': 36, 'Enalapril': 37, 'Rifampicin': 38, 'Gabapentin': 39,
    'Paroxetine': 40, 'Clonazepam': 41, 'Dexamethasone': 42, 'Mefenamic Acid': 43, 'Baclofen': 44,
    'Ondansetron': 45, 'Tadalafil': 46, 'Valacyclovir': 47, 'Etoricoxib': 48, 'Esomeprazole': 49,
    'Phenylephrine': 50, 'Mirtazapine': 51, 'Amantadine': 52, 'Azathioprine': 53, 'Betamethasone': 54,
    'Nifedipine': 55, 'Nortriptyline': 56, 'Diazepam': 57, 'Fluoxetine': 58, 'Levofloxacin': 59,
    'Nystatin': 60, 'Pregabalin': 61, 'Rosuvastatin': 62, 'Sildenafil': 63
}
season_map = {'Winter': 1, 'Summer': 5, 'Monsoon': 8}

typical_avg_daily_demand = {
    ('Mumbai', 'Insulin', 'Winter'): 50,
    ('Mumbai', 'Insulin', 'Summer'): 90,
    ('Mumbai', 'Insulin', 'Monsoon'): 70,
    ('Mumbai', 'Atorvastatin', 'Winter'): 25,
    ('Mumbai', 'Atorvastatin', 'Summer'): 35,
    ('Mumbai', 'Atorvastatin', 'Monsoon'): 30,
    ('Delhi', 'Paracetamol', 'Winter'): 110,
    ('Delhi', 'Paracetamol', 'Summer'): 80,
    ('Delhi', 'Paracetamol', 'Monsoon'): 90,
    ('Chennai', 'Amoxicillin', 'Winter'): 45,
    ('Chennai', 'Amoxicillin', 'Summer'): 55,
    ('Chennai', 'Amoxicillin', 'Monsoon'): 50,
    ('Kolkata', 'Aspirin', 'Winter'): 40,
    ('Kolkata', 'Aspirin', 'Summer'): 30,
    ('Kolkata', 'Aspirin', 'Monsoon'): 35,
    ('Banglore', 'Metformin', 'Winter'): 70,
    ('Banglore', 'Metformin', 'Summer'): 65,
    ('Banglore', 'Metformin', 'Monsoon'): 75,
}
typical_stock_level = {
    ('Mumbai', 'Insulin', 'Winter'): 20,
    ('Mumbai', 'Insulin', 'Summer'): 14,
    ('Mumbai', 'Insulin', 'Monsoon'): 3,
    ('Mumbai', 'Atorvastatin', 'Winter'): 5,
    ('Mumbai', 'Atorvastatin', 'Summer'): 8,
    ('Mumbai', 'Atorvastatin', 'Monsoon'): 7,
    ('Delhi', 'Paracetamol', 'Winter'): 20,
    ('Delhi', 'Paracetamol', 'Summer'): 12,
    ('Delhi', 'Paracetamol', 'Monsoon'): 11,
    ('Chennai', 'Amoxicillin', 'Winter'): 20,
    ('Chennai', 'Amoxicillin', 'Summer'): 9,
    ('Chennai', 'Amoxicillin', 'Monsoon'): 22,
    ('Kolkata', 'Aspirin', 'Winter'): 15,
    ('Kolkata', 'Aspirin', 'Summer'): 1,
    ('Kolkata', 'Aspirin', 'Monsoon'): 12,
    ('Banglore', 'Metformin', 'Winter'): 35,
    ('Banglore', 'Metformin', 'Summer'): 2,
    ('Banglore', 'Metformin', 'Monsoon'): 17,
}
# Blockchain Configuration - Updated with your new contract address
BLOCKCHAIN_CONFIG = {
    'provider_url': 'http://127.0.0.1:8545',
    'contract_address': "0x8A791620dd6260079BF849Dc5567aDC3F2FdC318",  # Your new deployed address
    'contract_abi_file': 'MedicineLedger.json'
}

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Web3 and contract with better error handling
def initialize_blockchain():
    """Initialize blockchain connection with comprehensive error handling"""
    try:
        # Test Web3 connection
        w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_CONFIG['provider_url']))
        
        if not w3.is_connected():
            raise Exception("Cannot connect to blockchain provider")
        
        logger.info(f"Connected to blockchain at {BLOCKCHAIN_CONFIG['provider_url']}")
        logger.info(f"Latest block: {w3.eth.block_number}")
        
        # Check if we have accounts
        if not w3.eth.accounts:
            raise Exception("No accounts available from blockchain provider")
        
        logger.info(f"Available accounts: {len(w3.eth.accounts)}")
        
        # Load contract ABI
        if not os.path.exists(BLOCKCHAIN_CONFIG['contract_abi_file']):
            raise Exception(f"Contract ABI file not found: {BLOCKCHAIN_CONFIG['contract_abi_file']}")
        
        with open(BLOCKCHAIN_CONFIG['contract_abi_file']) as f:
            contract_data = json.load(f)
            contract_abi = contract_data.get('abi')
            
        if not contract_abi:
            raise Exception("ABI not found in contract file")
        
        # Initialize contract
        contract = w3.eth.contract(
            address=w3.to_checksum_address(BLOCKCHAIN_CONFIG['contract_address']), 
            abi=contract_abi
        )
        
        # Test contract connection by calling a simple function
        try:
            # Try to call a view function to test the contract
            stock_count = contract.functions.getStockCount().call()
            logger.info(f"Contract connection successful. Stock count: {stock_count}")
        except Exception as e:
            logger.warning(f"Contract function test failed: {e}")
            # Continue anyway as contract might be deployed but empty
        
        # Use the first Hardhat account
        default_account = w3.eth.accounts[0]
        logger.info(f"Using default account: {default_account}")
        
        return w3, contract, default_account, True
        
    except FileNotFoundError as e:
        logger.error(f"Blockchain file not found: {e}")
        return None, None, None, False
    except Exception as e:
        logger.error(f"Blockchain connection failed: {e}")
        return None, None, None, False

# Initialize blockchain components
w3, contract, default_account, blockchain_enabled = initialize_blockchain()

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

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

# Correct haversine distance function
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)*2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)*2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# Blockchain helper functions with improved error handling
def get_user_blockchain_account(user_id):
    """Get or create a blockchain account for a user"""
    if not blockchain_enabled or not w3 or not w3.eth.accounts:
        return None
    
    try:
        account_index = user_id % len(w3.eth.accounts)
        return w3.eth.accounts[account_index]
    except Exception as e:
        logger.error(f"Error getting user blockchain account: {e}")
        return w3.eth.accounts[0] if w3.eth.accounts else None

def record_to_blockchain(action_type, data):
    """Record important actions to blockchain with improved error handling"""
    if not blockchain_enabled or not contract:
        logger.warning("Blockchain disabled - action not recorded to blockchain")
        return None
    
    try:
        user_account = get_user_blockchain_account(session.get('user_id', 0))
        if not user_account:
            logger.error("No user account available for blockchain transaction")
            return None
        
        if action_type == 'stock_update':
            tx_hash = contract.functions.addMedicineStock(
                data['pharmacy_name'],
                data['medicine_name'],
                data['quantity'],
                data['price']
            ).transact({'from': user_account, 'gas': 300000})
            
        elif action_type == 'shortage_report':
            tx_hash = contract.functions.reportShortage(
                data['medicine_name'],
                data['location_name']
            ).transact({'from': user_account, 'gas': 300000})
        
        else:
            logger.warning(f"Unknown blockchain action type: {action_type}")
            return None
        
        # Wait for transaction receipt with timeout
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            logger.info(f"Blockchain transaction successful: {receipt.transactionHash.hex()}")
            return receipt.transactionHash.hex()
        except Exception as e:
            logger.error(f"Transaction receipt error: {e}")
            return tx_hash.hex() if hasattr(tx_hash, 'hex') else str(tx_hash)
        
    except Exception as e:
        logger.error(f"Blockchain transaction failed: {e}")
        return None

def get_blockchain_data():
    """Fetch data from blockchain with improved error handling"""
    if not blockchain_enabled or not contract:
        return {'stocks': [], 'shortages': [], 'orders': [], 'enabled': False, 'error': 'Blockchain not available'}
    
    try:
        # Test contract connection first
        try:
            stock_count = contract.functions.getStockCount().call()
        except Exception as e:
            logger.error(f"Cannot call getStockCount: {e}")
            return {'stocks': [], 'shortages': [], 'orders': [], 'enabled': False, 'error': 'Contract call failed'}
        
        # Get shortage and order counts
        try:
            shortage_count = contract.functions.getShortageCount().call()
        except Exception as e:
            logger.warning(f"Cannot call getShortageCount: {e}")
            shortage_count = 0
            
        try:
            order_count = contract.functions.getOrderCount().call()
        except Exception as e:
            logger.warning(f"Cannot call getOrderCount: {e}")
            order_count = 0
        
        # Fetch all stock updates
        stock_list = []
        for i in range(min(stock_count, 100)):  # Limit to prevent timeouts
            try:
                stock = contract.functions.stockUpdates(i).call()
                stock_list.append({
                    "pharmacy": stock[0],
                    "medicine": stock[1],
                    "quantity": stock[2],
                    "price": stock[3],
                    "timestamp": stock[4]
                })
            except Exception as e:
                logger.warning(f"Error fetching stock {i}: {e}")
                continue
        
        # Fetch all shortage reports
        shortage_list = []
        for i in range(min(shortage_count, 100)):  # Limit to prevent timeouts
            try:
                report = contract.functions.shortageReports(i).call()
                shortage_list.append({
                    "medicine": report[0],
                    "location": report[1],
                    "timestamp": report[2]
                })
            except Exception as e:
                logger.warning(f"Error fetching shortage {i}: {e}")
                continue
        
        # Fetch all orders
        order_list = []
        for i in range(min(order_count, 100)):  # Limit to prevent timeouts
            try:
                order = contract.functions.getOrder(i).call()
                order_list.append({
                    "medicine": order[0],
                    "quantity": order[1],
                    "retailer": order[2],
                    "manufacturer": order[3],
                    "status": order[4]
                })
            except Exception as e:
                logger.warning(f"Error fetching order {i}: {e}")
                continue
        
        logger.info(f"Successfully fetched blockchain data: {len(stock_list)} stocks, {len(shortage_list)} shortages, {len(order_list)} orders")
        
        return {
            'stocks': stock_list,
            'shortages': shortage_list,
            'orders': order_list,
            'enabled': True,
            'total_stocks': stock_count,
            'total_shortages': shortage_count,
            'total_orders': order_count
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch blockchain data: {e}")
        return {
            'stocks': [], 
            'shortages': [], 
            'orders': [], 
            'enabled': False,
            'error': str(e)
        }

def update_retailer_stock_blockchain(medicine_name, new_stock):
    """Update retailer stock on blockchain"""
    if not blockchain_enabled or not contract:
        return None
    
    try:
        user_account = get_user_blockchain_account(session.get('user_id', 0))
        if not user_account:
            return None
        
        # Call the updateRetailerStock function
        tx_hash = contract.functions.updateRetailerStock(
            medicine_name,
            new_stock
        ).transact({'from': user_account, 'gas': 300000})
        
        # Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        logger.info(f"Retailer stock update successful: {receipt.transactionHash.hex()}")
        return receipt.transactionHash.hex()
        
    except Exception as e:
        logger.error(f"Blockchain retailer stock update failed: {e}")
        return None

def get_retailer_stock_from_blockchain(retailer_address, medicine_name):
    """Get retailer stock from blockchain"""
    if not blockchain_enabled or not contract:
        return 0
    
    try:
        stock = contract.functions.retailerStocks(retailer_address, medicine_name).call()
        return stock
    except Exception as e:
        logger.error(f"Failed to get retailer stock from blockchain: {e}")
        return 0

def sync_auto_orders():
    """Sync new auto-orders from blockchain into SQLite"""
    if not blockchain_enabled or not contract:
        return

    try:
        order_count = contract.functions.getOrderCount().call()
        conn = get_db_connection()

        for i in range(min(order_count, 100)):  # Limit to prevent timeouts
            try:
                order = contract.functions.getOrder(i).call()
                medicine_name, quantity, retailer_addr, manufacturer_addr, status = order

                blockchain_order_id = f"{retailer_addr}_{medicine_name}_{i}"
                existing = conn.execute(
                    "SELECT id FROM manufacturer_orders WHERE blockchain_order_id = ?",
                    (blockchain_order_id,)
                ).fetchone()

                if not existing:
                    # Get medicine ID with error handling
                    med = conn.execute("SELECT id FROM medicines WHERE name = ?", (medicine_name,)).fetchone()
                    if not med:
                        logger.warning(f"Medicine '{medicine_name}' not found in database")
                        continue

                    conn.execute("""
                        INSERT INTO manufacturer_orders (blockchain_order_id, medicine_id, quantity_ordered, retailer_address, manufacturer_address, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (blockchain_order_id, med["id"], quantity, retailer_addr, manufacturer_addr, status))
            except Exception as e:
                logger.error(f"Error processing order {i}: {e}")
                continue

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"sync_auto_orders error: {e}")

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
    blockchain_data = get_blockchain_data()
    return render_template('index.html', blockchain_data=blockchain_data)

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

@app.template_filter('datefmt')
def datefmt(value, format="%Y-%m-%d"):
    if not value:
        return ''
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(format)
@app.route('/api/search_pharmacies', methods=['POST'])
def api_search_pharmacies():
    data = request.get_json()
    user_lat = data.get('latitude')
    user_lon = data.get('longitude')
    medicines = [m.strip().lower() for m in data.get('medicines', [])]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT p.id, p.pharmacy_name, p.latitude, p.longitude, pm.medicine_name, pm.price
        FROM pharmacies p
        JOIN pharmacy_medicines pm ON p.id = pm.pharmacy_id
    ''')

    rows = cursor.fetchall()
    conn.close()

    results = {}
    for pid, pname, plat, plon, med_name, price in rows:
        if med_name.lower() in medicines:
            distance = haversine(user_lat, user_lon, plat, plon)
            if distance <= 20:  # 20 km radius
                if pid not in results:
                    results[pid] = {
                        "pharmacy_name": pname,
                        "latitude": plat,
                        "longitude": plon,
                        "medicines": []
                    }
                results[pid]["medicines"].append({
                    "medicine_name": med_name,
                    "price": price
                })

    if not results:
        return jsonify({"message": "No pharmacies found nearby with requested medicines."}), 404

    return jsonify({"pharmacies": list(results.values())})


location_cache = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Bangalore":(12.97,77.59),
    "Kolkata":(22.57, 88.36),
    "Hyderabad": (17.38, 78.48)
    # Add more if needed
}

@app.route('/search_pharmacies')
def search_pharmacies():
    user_location_str = request.args.get('location')
    user_location_str = user_location_str.strip().lower()
    user_latlng = location_cache.get(user_location_str)
    medicines_str = request.args.get('medicines')
    
    
    if not user_location_str or not medicines_str:
        return jsonify({"error": "Missing parameters"}), 400

    user_location_str = user_location_str.strip().title()

    user_latlng = location_cache.get(user_location_str)
    if not user_latlng:
        return jsonify({"error": "Invalid location"}), 400

    requested_medicines = [m.strip().lower() for m in medicines_str.split(',')]

    # Expanded dummy pharmacy data
    dummy_pharmacies = [
        # Mumbai
        {
            "id": 1,
            "pharmacy_name": "Test Pharmacy Mumbai",
            "address": "123 Test St, Mumbai",
            "latitude": 19.07,
            "longitude": 72.88,
            "medicine_prices": {
                "insulin": 500,
                "thyroxine": 300,
                "paracetamol": 20
            }
        },
        {
            "id": 4,
            "pharmacy_name": "mumb Care Pharmacy",
            "address": "78 Shahdara, Delhi",
            "latitude": 19.07,
            "longitude": 72.88,
            "medicine_prices": {
                "thyroxine": 310,
                "paracetamol": 25
            }
        },
        {
            "id": 2,
            "pharmacy_name": "Another Pharmacy Mumbai",
            "address": "456 Sample Rd, Mumbai",
            "latitude": 19.09,
            "longitude": 72.86,
            "medicine_prices": {
                "insulin": 520,
                "amoxicillin": 40
            }
        },
        {
            "id": 6,
            "pharmacy_name": "HealthMart Pharmacy mira bhayandar",
            "address": "50 MG Road, mmr",
            "latitude": 19.07,
            "longitude": 72.88,
            "medicine_prices": {
                "insulin": 495,
                "thyroxine": 305,
                "amoxicillin": 45
            }
        },

        {
            "id": 7,
            "pharmacy_name": "Wellness Pharmacy navi mumbai",
            "address": "22 Park Street, mmr",
            "latitude": 19.07,
            "longitude": 72.88,
            "medicine_prices": {
                "paracetamol": 23,
                "thyroxine": 320
            }
        },

        # Delhi
        {
            "id": 3,
            "pharmacy_name": "Fortis Pharmacy Delhi",
            "address": "45 Connaught Place, Delhi",
            "latitude": 28.63,
            "longitude": 77.21,
            "medicine_prices": {
                "insulin": 510,
                "amoxicillin": 42,
                "paracetamol": 22
            }
        },
        
        {
            "id": 4,
            "pharmacy_name": "Delhi Care Pharmacy",
            "address": "78 Shahdara, Delhi",
            "latitude": 28.66,
            "longitude": 77.25,
            "medicine_prices": {
                "thyroxine": 310,
                "paracetamol": 25
            }
        },
        {
            "id": 5,
            "pharmacy_name": "CarePlus Pharmacy Newdelhi",
            "address": "78 Anna Salai, ncr",
            "latitude": 28.63,
            "longitude": 77.21,
            "medicine_prices": {
                "amoxicillin": 48,
                "paracetamol": 20
            }
        },

        {
            "id": 5,
            "pharmacy_name": "CarePlus Pharmacy ncr",
            "address": "78 Anna Salai, noida",
            "latitude": 28.63,
            "longitude": 77.21,
            "medicine_prices": {
                "amoxicillin": 48,
                "paracetamol": 20
            }
        },

        # Bangalore
        {
            "id": 6,
            "pharmacy_name": "HealthMart Pharmacy Bangalore",
            "address": "50 MG Road, Bangalore",
            "latitude": 12.97,
            "longitude": 77.59,
            "medicine_prices": {
                "insulin": 495,
                "thyroxine": 305,
                "amoxicillin": 45
            }
        },

        # Kolkata
        {
            "id": 7,
            "pharmacy_name": "Wellness Pharmacy Kolkata",
            "address": "22 Park Street, Kolkata",
            "latitude": 22.57,
            "longitude": 88.36,
            "medicine_prices": {
                "paracetamol": 23,
                "thyroxine": 320
            }
        },

        # Hyderabad
        {
            "id": 8,
            "pharmacy_name": "MediCare Pharmacy Hyderabad",
            "address": "90 Banjara Hills, Hyderabad",
            "latitude": 17.38,
            "longitude": 78.48,
            "medicine_prices": {
                "insulin": 485,
                "amoxicillin": 50
            }
        },
        
    {
        "id": 9,
        "pharmacy_name": "Health Plus Pharmacy",
        "address": "Andheri West, Mumbai",
        "latitude": 19.1197,
        "longitude": 72.8468,
        "medicine_prices": {
            "paracetamol": 25.0,
            "amoxicillin": 50.0,
            "thyroxine": 310.0,
            "insulin": 490.0
        }
    },
    {
        "id": 10,
        "pharmacy_name": "Lifeline Medicals",
        "address": "Bandra East, Mumbai",
        "latitude": 19.0546,
        "longitude": 72.8409,
        "medicine_prices": {
            "paracetamol": 22.5,
            "amoxicillin": 48.0,
            "thyroxine": 305.0,
            "insulin": 495.0
        }
    },
    {
        "id": 11,
        "pharmacy_name": "Apollo Pharmacy",
        "address": "Lajpat Nagar, New Delhi",
        "latitude": 28.5672,
        "longitude": 77.2436,
        "medicine_prices": {
            "paracetamol": 24.0,
            "amoxicillin": 47.0,
            "thyroxine": 300.0,
            "insulin": 500.0
        }
    },
    {
        "id": 12,
        "pharmacy_name": "City Medicos",
        "address": "Connaught Place, New Delhi",
        "latitude": 28.6315,
        "longitude": 77.2167,
        "medicine_prices": {
            "paracetamol": 23.0,
            "amoxicillin": 45.5,
            "thyroxine": 315.0,
            "insulin": 510.0
        }
    }

    ]

    max_distance_km = 15
    nearby_pharmacies = []

    for pharmacy in dummy_pharmacies:
        pharmacy_latlng = (pharmacy['latitude'], pharmacy['longitude'])
        dist = geodesic(user_latlng, pharmacy_latlng).km
        if dist <= max_distance_km:
            med_prices = {med: price for med, price in pharmacy['medicine_prices'].items() if med in requested_medicines}
            if med_prices:
                nearby_pharmacies.append({
                    "pharmacy_name": pharmacy['pharmacy_name'],
                    "address": pharmacy['address'],
                    "latitude": pharmacy['latitude'],
                    "longitude": pharmacy['longitude'],
                    "medicine_prices": med_prices,
                    "distance_km": round(dist, 2)
                })

    nearby_pharmacies.sort(key=lambda x: x['distance_km'])
    print("Nearby pharmacies found:", len(nearby_pharmacies))
    if not nearby_pharmacies:
        print("No pharmacies found nearby with requested medicines.")

    return jsonify({
        "user_location": {"lat": user_latlng[0], "lng": user_latlng[1]},
        "pharmacies": nearby_pharmacies
    })



@app.route('/map')
def map():
    try:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT pharmacy_name, address, latitude, longitude FROM pharmacies")
        pharmacies = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
        pharmacies = []  # fallback to empty list so template rendering doesn't break

    return render_template('map.html', pharmacies=pharmacies)
# Add a blockchain status route for debugging
@app.route('/blockchain/status')
@login_required
def blockchain_status():
    """Check blockchain connection status"""
    status = {
        'enabled': blockchain_enabled,
        'provider_url': BLOCKCHAIN_CONFIG['provider_url'],
        'contract_address': BLOCKCHAIN_CONFIG['contract_address']
    }
    
    if blockchain_enabled and w3:
        try:
            status.update({
                'connected': w3.is_connected(),
                'latest_block': w3.eth.block_number,
                'accounts_count': len(w3.eth.accounts),
                'default_account': default_account
            })
            
            if contract:
                try:
                    stock_count = contract.functions.getStockCount().call()
                    status['contract_responsive'] = True
                    status['stock_count'] = stock_count
                except Exception as e:
                    status['contract_responsive'] = False
                    status['contract_error'] = str(e)
        except Exception as e:
            status['connection_error'] = str(e)
    
    return jsonify(status)

# Continue with all your existing routes...
# (I'm keeping the rest of your routes as they were, just adding the improved blockchain handling)

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
@app.route('/alternate-medicine')
def alternate_medicine():
    """Page for finding alternate medicines"""
    # Get all available medicines for search suggestions
    available_medicines = []
    if df is not None:
        available_medicines = sorted(df["Medicine Name"].unique().tolist())
    
    return render_template('alternate_medicine.html', medicines=available_medicines)

@app.route('/api/search-alternatives', methods=['POST'])
def search_alternatives():
    """API endpoint to get alternative medicines"""
    data = request.get_json()
    medicine_name = data.get('medicine_name', '').strip()
    
    if not medicine_name:
        return jsonify({'error': 'Medicine name is required'}), 400
    
    # Check if dataset is loaded
    if df is None:
        return jsonify({'error': 'Medicine database not available'}), 500
    
    # Find exact match or similar name
    medicine_found = None
    for med in df["Medicine Name"].values:
        if medicine_name.lower() == med.lower():
            medicine_found = med
            break
    
    # If exact match not found, try partial match
    if not medicine_found:
        for med in df["Medicine Name"].values:
            if medicine_name.lower() in med.lower() or med.lower() in medicine_name.lower():
                medicine_found = med
                break
    
    if not medicine_found:
        return jsonify({'error': f'Medicine "{medicine_name}" not found in database'}), 404
    
    main_med, similar_meds = get_similar_medicines(medicine_found)
    
    if main_med is None:
        return jsonify({'error': 'Could not find alternatives'}), 404
    
    return jsonify({
        'main_medicine': main_med,
        'alternatives': similar_meds,
        'total_found': len(similar_meds)
    })

@app.route('/api/medicine-suggestions')
def medicine_suggestions():
    """API endpoint for medicine name autocomplete"""
    query = request.args.get('q', '').lower()
    
    if not query or df is None:
        return jsonify([])
    
    # Filter medicines that contain the query
    suggestions = [
        med for med in df["Medicine Name"].values 
        if query in med.lower()
    ][:10]  # Limit to 10 suggestions
    
    return jsonify(suggestions)

# Add this route for detailed medicine info
@app.route('/medicine-details/<medicine_name>')
def medicine_details(medicine_name):
    """Detailed view of a specific medicine with alternatives"""
    if df is None:
        flash('Medicine database not available', 'error')
        return redirect(url_for('alternate_medicine'))
    
    main_med, similar_meds = get_similar_medicines(medicine_name)
    
    if main_med is None:
        flash(f'Medicine "{medicine_name}" not found', 'error')
        return redirect(url_for('alternate_medicine'))
    
    return render_template('medicine_details.html', 
                         main_medicine=main_med, 
                         alternatives=similar_meds)

# Helper function to parse composition ingredients
def parse_composition(composition):
    """Parse medicine composition into individual ingredients"""
    if not composition or pd.isna(composition):
        return []
    
    ingredients = []
    # Split by common delimiters
    parts = re.split(r'[+,&]', str(composition))
    
    for part in parts:
        part = part.strip()
        if part:
            # Extract ingredient name and dosage
            match = re.search(r'(.+?)\s*(\d+\.?\d*)\s*(mg|g|mcg|ml|%)?', part, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                dosage = match.group(2)
                unit = match.group(3) or 'mg'
                ingredients.append({
                    'name': name,
                    'dosage': float(dosage),
                    'unit': unit,
                    'full_text': part
                })
            else:
                ingredients.append({
                    'name': part,
                    'dosage': 0,
                    'unit': '',
                    'full_text': part
                })
    
    return ingredients

# Add this template filter to your app
@app.template_filter('parse_ingredients')
def parse_ingredients_filter(composition):
    return parse_composition(composition)

@app.route('/admin/dashboard')
@login_required
@role_required(['admin'])
def admin_dashboard():
    """Admin dashboard with system overview"""
    # Get system statistics with error handling
    try:
        total_users = execute_query('SELECT COUNT(*) as count FROM users')
        total_pharmacies = execute_query('SELECT COUNT(*) as count FROM pharmacies')
        total_medicines = execute_query('SELECT COUNT(*) as count FROM medicines')
        active_alerts = execute_query('SELECT COUNT(*) as count FROM shortage_alerts WHERE is_active = TRUE')
        total_reports = execute_query('SELECT COUNT(*) as count FROM patient_reports')
        
        stats = {
            'total_users': total_users[0]['count'] if total_users else 0,
            'total_pharmacies': total_pharmacies[0]['count'] if total_pharmacies else 0,
            'total_medicines': total_medicines[0]['count'] if total_medicines else 0,
            'active_alerts': active_alerts[0]['count'] if active_alerts else 0,
            'total_reports': total_reports[0]['count'] if total_reports else 0
        }
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        stats = {
            'total_users': 0,
            'total_pharmacies': 0,
            'total_medicines': 0,
            'active_alerts': 0,
            'total_reports': 0
        }
    
    # Get blockchain data
    blockchain_data = get_blockchain_data()
    
    # Get recent alerts
    recent_alerts = execute_query('''
        SELECT sa.*, m.name as medicine_name, l.name as location_name
        FROM shortage_alerts sa
        JOIN medicines m ON sa.medicine_id = m.id
        JOIN locations l ON sa.location_id = l.id
        WHERE sa.is_active = TRUE
        ORDER BY sa.created_at DESC LIMIT 10
    ''') or []
    
    # Get recent reports
    recent_reports = execute_query('''
        SELECT pr.*, m.name as medicine_name, l.name as location_name, u.full_name as reporter_name
        FROM patient_reports pr
        JOIN medicines m ON pr.medicine_id = m.id
        JOIN locations l ON pr.location_id = l.id
        LEFT JOIN users u ON pr.user_id = u.id
        ORDER BY pr.created_at DESC LIMIT 10
    ''') or []
    
    return render_template('admin_dashboard.html', 
                         stats=stats, 
                         blockchain_data=blockchain_data,
                         recent_alerts=recent_alerts,
                         recent_reports=recent_reports)
@app.route('/pharmacy/dashboard')
@login_required
@role_required(['pharmacy'])
def pharmacy_dashboard():
    """Pharmacy dashboard for inventory management"""
    user_id = session.get('user_id')
    
    # Sync auto-orders from blockchain
    sync_auto_orders()
    
    # Get pharmacy info with error handling
    pharmacy_result = execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,))
    pharmacy = pharmacy_result[0] if pharmacy_result else None
    
    if not pharmacy:
        flash('Pharmacy profile not found. Please complete your profile.', 'warning')
        return redirect(url_for('pharmacy_profile'))
    
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
    
    # Get blockchain data for this pharmacy
    blockchain_data = get_blockchain_data()
    
    return render_template('pharmacy_dashboard.html', 
                         pharmacy=pharmacy,
                         inventory=inventory,
                         low_stock=low_stock,
                         blockchain_data=blockchain_data)

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
    
    # Get active alerts in user's area
    active_alerts = execute_query('''
        SELECT sa.*, m.name as medicine_name, l.name as location_name
        FROM shortage_alerts sa
        JOIN medicines m ON sa.medicine_id = m.id
        JOIN locations l ON sa.location_id = l.id
        WHERE sa.is_active = TRUE
        ORDER BY sa.severity DESC, sa.created_at DESC
        LIMIT 10
    ''')
    
    # Get blockchain data
    blockchain_data = get_blockchain_data()
    
    return render_template('patient_dashboard.html', 
                         my_reports=my_reports,
                         active_alerts=active_alerts,
                         blockchain_data=blockchain_data)

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
    
    # Get blockchain data
    blockchain_data = get_blockchain_data()
    
    return render_template('authority_dashboard.html', 
                         critical_alerts=critical_alerts,
                         shortage_stats=shortage_stats,
                         blockchain_data=blockchain_data)

@app.route('/predict_medicine', methods=['GET', 'POST'])
def predict_medicine():
    if request.method == 'POST':
        region = request.form.get('region')
        medicine = request.form.get('medicine')
        season = request.form.get('season')

        # Validate inputs
        if region not in region_map or medicine not in medicine_map or season not in season_map:
            flash("Invalid input", "error")
            return render_template('predict_medicine.html')

        key = (region, medicine, season)
        avg_daily_demand = typical_avg_daily_demand.get(key, 100)  # default fallback
        stock_level = typical_stock_level.get(key, 50)             # default fallback

        X = pd.DataFrame([{
            'Month': season_map[season],
            'Region_Code': region_map[region],
            'Medicine_Code': medicine_map[medicine],
            'Avg_Daily_Demand': avg_daily_demand,
            'Stock_Level': stock_level,
        }])

        shortage_pred = model_shortage.predict(X)[0]
        price_spike_pred = model_price.predict(X)[0]

        result = {
            'region': region,
            'medicine': medicine,
            'season': season,
            'shortage': int(shortage_pred),
            'price_spike': int(price_spike_pred)
        }
        return render_template('predict_medicine.html', result=result)

    # GET request
    return render_template('predict_medicine.html')

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
        
        # Insert into database
        report_id = execute_insert('''
            INSERT INTO patient_reports (user_id, medicine_id, location_id, report_type, 
                                       pharmacy_id, reported_price, expected_price, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], medicine_id, location_id, report_type, 
              pharmacy_id, reported_price, expected_price, description))
        
        if report_id:
            # Record shortage report to blockchain
            if report_type == 'shortage':
                medicine_name = execute_query('SELECT name FROM medicines WHERE id = ?', (medicine_id,))[0]['name']
                location_name = execute_query('SELECT name FROM locations WHERE id = ?', (location_id,))[0]['name']
                
                blockchain_tx = record_to_blockchain('shortage_report', {
                    'medicine_name': medicine_name,
                    'location_name': location_name
                })
                
                if blockchain_tx:
                    # Update the report with blockchain transaction hash
                    execute_query('''
                        UPDATE patient_reports 
                        SET blockchain_hash = ? 
                        WHERE id = ?
                    ''', (blockchain_tx, report_id))
            
            flash('Report submitted successfully!', 'success')
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
    
    # Debug: Print user_id
    print(f"Debug - User ID: {user_id}")
    
    pharmacy_result = execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,))
    
    # Debug: Print pharmacy result
    print(f"Debug - Pharmacy result: {pharmacy_result}")
   
    if not pharmacy_result:
        flash('Pharmacy profile not found. Please complete your profile first.', 'warning')
        return redirect(url_for('pharmacy_profile'))
   
    pharmacy = pharmacy_result[0]
    
    # Check if pharmacy profile is complete (add required fields check)
    required_fields = ['pharmacy_name', 'address', 'phone', 'email', 'license_number']
    missing_fields = [field for field in required_fields if not pharmacy.get(field)]
    
    if missing_fields:
        flash(f'Please complete your pharmacy profile. Missing: {", ".join(missing_fields)}', 'warning')
        return redirect(url_for('pharmacy_profile'))
   
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
                         medicines=medicines or [],
                         inventory=inventory or [],
                         pharmacy=pharmacy)

@app.route('/inventory/update', methods=['POST'])
@login_required
@role_required(['pharmacy'])
def update_inventory():
    """API endpoint to update pharmacy inventory"""
    user_id = session.get('user_id')
    pharmacy_result = execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,))
    
    if not pharmacy_result:
        flash('Pharmacy profile not found. Please complete your profile first.', 'error')
        return redirect(url_for('pharmacy_profile'))
    
    pharmacy = pharmacy_result[0]
    
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
    
    # Get medicine name for blockchain update with error handling
    medicine_result = execute_query('SELECT name FROM medicines WHERE id = ?', (medicine_id,))
    if not medicine_result:
        flash('Medicine not found!', 'error')
        return redirect(url_for('manage_inventory'))
    
    medicine_name = medicine_result[0]['name']
    
    # Update retailer stock on blockchain (new functionality)
    blockchain_tx = update_retailer_stock_blockchain(medicine_name, int(current_stock))
    
    # Also record stock update to blockchain (existing functionality)
    blockchain_tx2 = record_to_blockchain('stock_update', {
        'pharmacy_name': pharmacy['pharmacy_name'],
        'medicine_name': medicine_name,
        'quantity': int(current_stock),
        'price': int(float(unit_price) * 100)  # Convert to paise/cents
    })
    
    if blockchain_tx or blockchain_tx2:
        flash(f'Inventory updated successfully! Blockchain transactions recorded.', 'success')
    else:
        flash('Inventory updated successfully!', 'success')
    
    # Sync auto-orders after inventory update
    sync_auto_orders()
    
    return redirect(url_for('manage_inventory'))
@app.route('/manufacturer/orders')
@login_required
@role_required(['admin', 'pharmacy'])
def manufacturer_orders():
    """View manufacturer orders from blockchain"""
    # Sync latest orders from blockchain
    sync_auto_orders()
    
    # Get orders from database
    orders = execute_query('''
        SELECT mo.*, m.name as medicine_name
        FROM manufacturer_orders mo
        JOIN medicines m ON mo.medicine_id = m.id
        ORDER BY mo.created_at DESC
    ''')
    
    return render_template('manufacturer_orders.html', orders=orders)
@app.route('/blockchain/data')
@login_required
def blockchain_data():
    """View blockchain data dashboard"""
    data = get_blockchain_data()
    
    # Format data for template
    formatted_data = {
        'enabled': data['enabled'],
        'stats': {
            'total_stocks': data.get('total_stocks', 0),
            'total_shortages': data.get('total_shortages', 0),
            'total_transactions': data.get('total_stocks', 0) + data.get('total_shortages', 0)
        },
        'recent_stocks': data.get('stocks', [])[-10:],  # Last 10
        'recent_shortages': data.get('shortages', [])[-10:],  # Last 10
        'stocks': data.get('stocks', []),
        'shortages': data.get('shortages', [])
    }
    
    return render_template('blockchain_dashboard.html', data=formatted_data)

@app.route('/api/blockchain/stats')
@login_required
def blockchain_stats():
    """API endpoint for blockchain statistics"""
    data = get_blockchain_data()
    return jsonify(data)

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
    
    return render_template('medicine_search.html', 
                         medicines=medicines, 
                         locations=locations,
                         search_results=search_results,
                         debug_info=debug_info if app.debug else None)

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
    
    # Get blockchain analytics
    blockchain_data = get_blockchain_data()
    
    return render_template('analytics.html', 
                         shortage_trends=shortage_trends,
                         top_shortage_medicines=top_shortage_medicines,
                         location_shortages=location_shortages,
                         blockchain_data=blockchain_data)

# Replace your existing profile route and add these routes to your app.py

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    user_id = session.get('user_id')
    user = execute_query('SELECT * FROM users WHERE id = ?', (user_id,))[0]
    
    # Redirect pharmacy users to their specific profile page
    if user['user_type'] == 'pharmacy':
        return redirect(url_for('pharmacy_profile'))
    
    return render_template('profile.html', user=user)

# Remove the duplicate pharmacy_profile routes and replace with this single, complete implementation:

@app.route('/pharmacy/profile', methods=['GET', 'POST'])
@login_required
@role_required(['pharmacy'])
def pharmacy_profile():
    """Pharmacy-specific profile page with pharmacy details"""
    user_id = session.get('user_id')
    
    # Debug
    print(f"Debug - User ID in pharmacy_profile: {user_id}")
    
    # Get user info with error handling
    user_result = execute_query('SELECT * FROM users WHERE id = ?', (user_id,))
    if not user_result:
        flash('User not found!', 'error')
        return redirect(url_for('login'))
    
    user = user_result[0]
    
    # Get pharmacy info
    pharmacy_result = execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,))
    pharmacy = pharmacy_result[0] if pharmacy_result else None
    
    # Debug
    print(f"Debug - Existing pharmacy: {pharmacy}")
    
    if request.method == 'POST':
        # Handle pharmacy profile update
        pharmacy_name = request.form.get('pharmacy_name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        email = request.form.get('email')
        license_number = request.form.get('license_number')
        location_id = request.form.get('location_id')
        latitude = request.form.get('latitude') or None
        longitude = request.form.get('longitude') or None
        
        # Debug
        print(f"Debug - Form data: {pharmacy_name}, {address}, {phone}, {email}, {license_number}")
        
        try:
            if pharmacy:
                # Update existing pharmacy
                execute_query('''
                    UPDATE pharmacies 
                    SET pharmacy_name = ?, address = ?, phone = ?, email = ?, 
                        license_number = ?, location_id = ?, latitude = ?, longitude = ?
                    WHERE user_id = ?
                ''', (pharmacy_name, address, phone, email, license_number, 
                      location_id, latitude, longitude, user_id))
                print("Debug - Updated existing pharmacy")
            else:
                # Create new pharmacy profile
                result = execute_insert('''
                    INSERT INTO pharmacies (user_id, pharmacy_name, address, phone, email, 
                                          license_number, location_id, latitude, longitude)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, pharmacy_name, address, phone, email, license_number, 
                      location_id, latitude, longitude))
                print(f"Debug - Created new pharmacy with ID: {result}")
            
            # Verify the save worked
            verify_result = execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,))
            print(f"Debug - Pharmacy after save: {verify_result}")
            
            flash('Pharmacy profile updated successfully!', 'success')
            return redirect(url_for('pharmacy_profile'))
            
        except Exception as e:
            print(f"Debug - Error saving pharmacy: {e}")
            flash('Error updating pharmacy profile!', 'error')
    
    # Get locations for dropdown
    locations = execute_query('SELECT * FROM locations ORDER BY name')
    
    return render_template('pharmacy_profile.html', user=user, pharmacy=pharmacy, locations=locations or [])
@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Handle profile updates for all user types"""
    user_id = session.get('user_id')
    user = execute_query('SELECT * FROM users WHERE id = ?', (user_id,))[0]
    
    if user['user_type'] == 'pharmacy':
        # Handle pharmacy profile update
        pharmacy_name = request.form.get('pharmacy_name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        email = request.form.get('email')
        license_number = request.form.get('license_number')
        location_id = request.form.get('location_id')
        latitude = request.form.get('latitude') or None
        longitude = request.form.get('longitude') or None
        
        # Check if pharmacy profile exists
        existing_pharmacy = execute_query('SELECT id FROM pharmacies WHERE user_id = ?', (user_id,))
        
        if existing_pharmacy:
            # Update existing pharmacy
            execute_query('''
                UPDATE pharmacies 
                SET pharmacy_name = ?, address = ?, phone = ?, email = ?, 
                    license_number = ?, location_id = ?, latitude = ?, longitude = ?
                WHERE user_id = ?
            ''', (pharmacy_name, address, phone, email, license_number, 
                  location_id, latitude, longitude, user_id))
        else:
            # Create new pharmacy profile
            execute_insert('''
                INSERT INTO pharmacies (user_id, pharmacy_name, address, phone, email, 
                                      license_number, location_id, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, pharmacy_name, address, phone, email, license_number, 
                  location_id, latitude, longitude))
        
        flash('Pharmacy profile updated successfully!', 'success')
        return redirect(url_for('pharmacy_profile'))
        
    else:
        # Handle regular user profile update
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        
        execute_query('''
            UPDATE users 
            SET full_name = ?, phone = ?
            WHERE id = ?
        ''', (full_name, phone, user_id))
        
        session['full_name'] = full_name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

@app.route('/profile/complete')
@login_required
def complete_profile():
    """Page to complete profile setup after registration"""
    user_id = session.get('user_id')
    user = execute_query('SELECT * FROM users WHERE id = ?', (user_id,))[0]
    
    if user['user_type'] == 'pharmacy':
        # Check if pharmacy profile is complete
        pharmacy = execute_query('SELECT * FROM pharmacies WHERE user_id = ?', (user_id,))
        if not pharmacy:
            flash('Please complete your pharmacy profile to continue.', 'warning')
            return redirect(url_for('pharmacy_profile'))
    
    return redirect(url_for('dashboard'))

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
    return render_template("map.html", pharmacies=json.dumps(pharmacies_list))

if __name__ == '__main__':
    # Initialize database if it doesn't exist
    if not os.path.exists('healthcare.db'):
        print("Database not found. Please run the schema script first.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
