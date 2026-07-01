import os
import json
from flask import Flask, render_template, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# Get secret key from .env, with a fallback
app.secret_key = os.environ.get("SECRET_KEY", "fallback_insecure_key")

# Google Sheets Connection
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get('GOOGLE_CREDENTIALS')

try:
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet_db = client.open("Santhosh_Sai_Krishna_Database")
except Exception as e:
    print("Database connection failed:", e)
    sheet_db = None

def get_settings():
    # Fallback settings so the website doesn't crash if the database disconnects
    if not sheet_db: 
        return {
            'Announcement_Bar': '⚠️ DATABASE NOT CONNECTED',
            'WhatsApp_Number': '', 'UPI_QR_Image_URL': '',
            'Carousel_Image_1': '', 'Carousel_Image_2': '', 'Carousel_Image_3': ''
        }
    try:
        settings_raw = sheet_db.worksheet("Site_Settings").get_all_records()
        return {row['Setting_Name']: row['Setting_Value'] for row in settings_raw}
    except Exception:
        return {}

@app.route('/')
def home():
    # Display a helpful error directly on the website if credentials are missing
    if not sheet_db:
        return "<h1>Server is Running! ✅</h1><h2 style='color:red;'>But Google Sheets Connection Failed ❌</h2><p>1. Make sure your <b>credentials.json</b> file is in the same folder as app.py.<br>2. Make sure you opened the <b>credentials.json</b> file, copied the 'client_email', and shared your Google Sheet with that email address.<br>3. Check your terminal for the exact error message.</p>"
    
    return render_template('index.html', settings=get_settings())

@app.route('/shop')
def shop():
    if not sheet_db: return "Database Error", 500
    products = sheet_db.worksheet("Products").get_all_records()
    
    # Process weights and format products
    for p in products:
        w_str = str(p.get('Weight_Volume', '1kg'))
        p['Weight_Options'] = [w.strip() for w in w_str.split(',') if w.strip()]
        
    return render_template('shop.html', products=products, settings=get_settings())

@app.route('/cart')
def cart():
    return render_template('cart.html', settings=get_settings())

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    settings = get_settings()
    if request.method == 'POST':
        password = request.form.get('password')
        
        # Check against the secure password stored in the .env file
        correct_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        if password == correct_password:
            orders = sheet_db.worksheet("Orders").get_all_records()
            coupons = sheet_db.worksheet("Shipping_&_Discounts").get_all_records()
            return render_template('admin.html', orders=orders[::-1], coupons=coupons, authenticated=True, settings=settings)
        return render_template('admin.html', error="Invalid Password", authenticated=False, settings=settings)
    
    return render_template('admin.html', authenticated=False, settings=settings)

@app.route('/api/update_order', methods=['POST'])
def update_order():
    data = request.json
    order_id = data['order_id']
    new_status = data['status']
    
    orders_sheet = sheet_db.worksheet("Orders")
    orders = orders_sheet.get_all_records()
    
    # Find row to update (adding 2 to account for 0-index and header row)
    for idx, order in enumerate(orders):
        if str(order['Order_ID']) == str(order_id):
            orders_sheet.update_cell(idx + 2, 9, new_status) # Column 9 is Order_Status
            return jsonify({"status": "success"})
            
    return jsonify({"status": "error", "message": "Order not found"})

@app.route('/api/toggle_coupon', methods=['POST'])
def toggle_coupon():
    data = request.json
    code = data['code']
    new_status = data['status']
    
    sheet = sheet_db.worksheet("Shipping_&_Discounts")
    records = sheet.get_all_records()
    
    for idx, row in enumerate(records):
        if str(row['Discount_Code']).upper() == code.upper():
            sheet.update_cell(idx + 2, 6, new_status) # Column 6 is Is_Active
            return jsonify({"status": "success"})
            
    return jsonify({"status": "error", "message": "Coupon not found"})

@app.route('/api/auth', methods=['POST'])
def auth():
    data = request.json
    customers_sheet = sheet_db.worksheet("Customers")
    customers = customers_sheet.get_all_records()
    
    if data['action'] == 'login':
        for c in customers:
            if str(c['Username']) == data['username'] and str(c['Password']) == data['password']:
                return jsonify({"status": "success", "user": c})
        return jsonify({"status": "error", "message": "Invalid username or password"})
        
    elif data['action'] == 'register':
        if any(c['Username'] == data['username'] for c in customers):
            return jsonify({"status": "error", "message": "Username already exists"})
        customers_sheet.append_row([data['username'], data['password'], data['name'], data['phone'], data['address'], data['pincode']])
        return jsonify({"status": "success"})

@app.route('/api/validate_checkout', methods=['POST'])
def validate_checkout():
    data = request.json
    pincode = str(data.get('pincode', '')).strip()
    discount_code = str(data.get('discount', '')).strip().upper()
    phone = str(data.get('phone', '')).strip()
    subtotal = float(data.get('subtotal', 0))
    
    try:
        shipping_sheet = sheet_db.worksheet("Shipping_&_Discounts").get_all_records()
    except Exception:
        shipping_sheet = []
        
    shipping_cost = 100 # Default shipping fee if pincode not found
    discount_percent = 0
    message = ""
    coupon_found = False
    
    for row in shipping_sheet:
        # 1. Check shipping cost independently
        if str(row.get('Pincode', '')).strip() == pincode:
            try:
                shipping_cost = int(row.get('Shipping_Cost', 0))
            except ValueError:
                shipping_cost = 0
                
        # 2. Check coupon independently
        row_discount = str(row.get('Discount_Code', '')).strip().upper()
        if discount_code and row_discount == discount_code:
            coupon_found = True
            is_active = str(row.get('Is_Active', '')).strip().upper()
            
            # Simple TRUE/FALSE check only
            if is_active in ['TRUE', '1', 'YES']:
                discount_percent = int(row.get('Discount_Percentage', 0))
                message = f"Coupon Applied! {discount_percent}% Off"
            else:
                message = "This coupon is currently disabled."
                
    if discount_code and not coupon_found:
        message = "Invalid or Expired Coupon"
        
    return jsonify({
        "shipping": shipping_cost, 
        "discount_percent": discount_percent, 
        "message": message
    })

@app.route('/api/place_order', methods=['POST'])
def place_order():
    data = request.json
    orders_sheet = sheet_db.worksheet("Orders")
    order_id = f"ORD{len(orders_sheet.get_all_values()) + 1000}"
    date = datetime.now().strftime("%Y-%m-%d")
    
    orders_sheet.append_row([
        order_id, date, data['username'], data['phone'], 
        data['items'], data['total'], data['address'], data['pincode'], "Received"
    ])
    return jsonify({"status": "success", "order_id": order_id})

if __name__ == '__main__':
    app.run(debug=True)