from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import secrets
from functools import wraps
from datetime import datetime, date, timedelta
import requests
import re
import random
import string
import json
import hashlib

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ============ SECRET KEY CONFIGURATION (UPDATED) ============
# Your secret key - stored in .env file
secret_key = os.getenv("SECRET_KEY")

if not secret_key:
    # Fallback - generate a key (for development only)
    secret_key = "8f3a2b1c9d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a"
    print("=" * 50)
    print("WARNING: No SECRET_KEY found in .env file!")
    print(f"Using default key: {secret_key[:20]}...")
    print("=" * 50)
else:
    print("✓ SECRET_KEY loaded successfully from .env file")

app.secret_key = secret_key

# ============ VERCEL COMPATIBILITY FIX ============
TMP_DIR = '/tmp/exam_saarthi'
os.makedirs(TMP_DIR, exist_ok=True)

IS_VERCEL = os.environ.get('VERCEL', False) or os.environ.get('NOW_REGION', False)

if IS_VERCEL:
    DB_FILE = os.path.join(TMP_DIR, "database.db")
    VISITOR_FILE = os.path.join(TMP_DIR, "visitors.json")
else:
    DB_FILE = "database.db"
    VISITOR_FILE = "visitors.json"

# ============ SESSION CONFIGURATION ============
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ============ ADMIN PASSWORD ============
admin_password = os.getenv("ADMIN_PASSWORD")
if not admin_password:
    admin_password = "admin123"
app.config["ADMIN_PASSWORD"] = admin_password

# ============ TELEGRAM BOT CONFIGURATION ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print("=" * 50)
print("Exam Saarthi - Configuration")
print(f"Secret Key: {'✓ Set' if app.secret_key else '✗ Missing'}")
print(f"Admin Password: {'✓ Set' if admin_password else '✗ Missing'}")
if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    print(f"Telegram Bot: ✓ Configured")
else:
    print("Telegram Bot: ✗ Not Configured")
print("=" * 50)

# ============ TELEGRAM FUNCTIONS ============

def send_telegram_message(chat_id, message):
    """Send message to Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def send_contact_message(name, email, university, course, message):
    """Send contact form message to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    current_time = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    
    msg = f"""
🔔 <b>NEW CONTACT FORM SUBMISSION</b> 🔔

👤 <b>Name:</b> {name}
📧 <b>Email:</b> {email}
🏛️ <b>University:</b> {university}
📚 <b>Course:</b> {course if course else 'Not specified'}

💬 <b>Message:</b>
{message}

━━━━━━━━━━━━━━━━━━━━━
⏰ <b>Time:</b> {current_time}
🌐 <b>Source:</b> Exam Saarthi Website
    """
    
    return send_telegram_message(TELEGRAM_CHAT_ID, msg)

# ============ VISITOR COUNTER FUNCTIONS ============

def load_visitor_data():
    if os.path.exists(VISITOR_FILE):
        try:
            with open(VISITOR_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"total": 0, "daily": {}, "history": {}}
    return {"total": 0, "daily": {}, "history": {}}

def save_visitor_data(data):
    with open(VISITOR_FILE, 'w') as f:
        json.dump(data, f)

def get_weekly_total(data):
    today = date.today()
    week_total = 0
    for i in range(7):
        d = today - timedelta(days=i)
        date_str = d.strftime('%Y-%m-%d')
        week_total += data.get("daily", {}).get(date_str, 0)
    return week_total

def get_monthly_total(data):
    today = date.today()
    current_month = today.strftime('%Y-%m')
    month_total = 0
    for date_str, count in data.get("daily", {}).items():
        if date_str.startswith(current_month):
            month_total += count
    return month_total

def update_visitor_count():
    data = load_visitor_data()
    today = str(date.today())
    
    visitor_ip = request.remote_addr
    visitor_key = f"{visitor_ip}_{today}"
    session_key = f"visited_{today}_{hashlib.md5(visitor_key.encode()).hexdigest()}"
    
    if "daily" not in data:
        data["daily"] = {}
    if today not in data["daily"]:
        data["daily"][today] = 0
    
    if not session.get(session_key):
        data["daily"][today] += 1
        data["total"] = data.get("total", 0) + 1
        session[session_key] = True
        save_visitor_data(data)
    
    return data

# ============ DATABASE CONNECTION ============

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db_exists = os.path.exists(DB_FILE)
    conn = get_db_connection()

    if not db_exists:
        conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            mobile TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.execute("""
        CREATE TABLE reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        print("Database created successfully!")
    else:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN fullname TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN mobile TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except:
            pass
        conn.commit()
    
    conn.close()

init_db()

# ============ CACHE CONTROL DECORATOR ============
def no_cache(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please login as admin first', 'danger')
            return redirect(url_for('admin'))
        return f(*args, **kwargs)
    return decorated_function

# ============ RESET TOKEN FUNCTIONS ============
def generate_reset_token():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def save_reset_token(email, token):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM reset_tokens WHERE email = ?", (email,))
        conn.execute("INSERT INTO reset_tokens (email, token) VALUES (?, ?)", (email, token))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving token: {e}")
        return False

def verify_reset_token(email, token):
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT * FROM reset_tokens WHERE email = ? AND token = ? AND created_at > datetime('now', '-1 hour')",
            (email, token)
        ).fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Error verifying token: {e}")
        return False

def delete_reset_token(email):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM reset_tokens WHERE email = ?", (email,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error deleting token: {e}")

# ============ CONTACT FORM HANDLER ============

@app.route("/submit_contact", methods=["POST"])
def submit_contact():
    try:
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        university = request.form.get("university", "").strip()
        course = request.form.get("course", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not university or not message:
            return jsonify({"success": False, "message": "Please fill all required fields"})

        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, email):
            return jsonify({"success": False, "message": "Please enter a valid email address"})

        print(f"Contact Form: {name} | {email} | {university}")

        # Send to Telegram if configured
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            success = send_contact_message(name, email, university, course, message)
            if success:
                return jsonify({"success": True, "message": "Message sent successfully! We'll get back to you soon."})
            else:
                return jsonify({"success": True, "message": "Thank you for contacting us! We have received your message."})
        else:
            return jsonify({"success": True, "message": "Thank you for contacting us! We'll get back to you soon."})

    except Exception as e:
        print(f"Error in contact form: {e}")
        return jsonify({"success": False, "message": "Unable to send message. Please try again later."})

# ============ AUTH ROUTES ============

@app.route("/register", methods=["GET", "POST"])
@no_cache
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([fullname, mobile, email, username, password]):
            flash("All fields are required", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (fullname, mobile, email, username, password) VALUES (?, ?, ?, ?, ?)",
                (fullname, mobile, email, username, hashed_password)
            )
            conn.commit()
            conn.close()
            flash("User Registered Successfully! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError as e:
            if "email" in str(e).lower():
                flash("Email already exists", "danger")
            else:
                flash("Username already exists", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
@no_cache
def login():
    if 'user_id' in session:
        return redirect(url_for("home"))
        
    if request.method == "POST":
        username_email = request.form.get("username_email", "").strip()
        password = request.form.get("password", "")

        if not username_email or not password:
            flash("Please enter both username/email and password", "danger")
            return redirect(url_for("login"))

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? OR email=?",
            (username_email, username_email)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["fullname"] = user["fullname"]
            session["email"] = user["email"]
            
            flash(f"Welcome back, {user['fullname']}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid Credentials", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
@no_cache
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))

# ============ MAIN ROUTES ============

@app.route("/")
@no_cache
def home():
    update_visitor_count()
    return render_template("index.html", user=session.get('username'))

@app.route("/about")
@no_cache
def about():
    return render_template("about.html", user=session.get('username'))

@app.route("/contact")
@no_cache
def contact():
    return render_template("contact.html", user=session.get('username'))

@app.route("/university")
@no_cache
def university():
    return render_template("university.html", user=session.get('username'))

# ============ IGU ROUTES ============

@app.route("/igu")
@no_cache
def igu():
    return render_template("igu.html", user=session.get('username'))

@app.route("/igu-btech")
@no_cache
def igu_btech():
    return render_template("igu-btech.html", user=session.get('username'))

@app.route("/igu-mtech")
@no_cache
def igu_mtech():
    return render_template("igu-mtech.html", user=session.get('username'))

@app.route("/igu-bca")
@no_cache
def igu_bca():
    return render_template("igu-bca.html", user=session.get('username'))

@app.route("/igu-bba")
@no_cache
def igu_bba():
    return render_template("igu-bba.html", user=session.get('username'))

@app.route("/igu-bsc")
@no_cache
def igu_bsc():
    return render_template("igu-bsc.html", user=session.get('username'))

@app.route("/igu-msc")
@no_cache
def igu_msc():
    return render_template("igu-msc.html", user=session.get('username'))

@app.route("/igu-ba")
@no_cache
def igu_ba():
    return render_template("igu-ba.html", user=session.get('username'))

@app.route("/igu-ma")
@no_cache
def igu_ma():
    return render_template("igu-ma.html", user=session.get('username'))

@app.route("/igu-bcom")
@no_cache
def igu_bcom():
    return render_template("igu-bcom.html", user=session.get('username'))

@app.route("/igu-mcom")
@no_cache
def igu_mcom():
    return render_template("igu-mcom.html", user=session.get('username'))

@app.route("/igu-bed")
@no_cache
def igu_bed():
    return render_template("igu-bed.html", user=session.get('username'))

@app.route("/igu-llb")
@no_cache
def igu_llb():
    return render_template("igu-llb.html", user=session.get('username'))

@app.route("/igu-mca")
@no_cache
def igu_mca():
    return render_template("igu-mca.html", user=session.get('username'))

@app.route("/igu-mba")
@no_cache
def igu_mba():
    return render_template("igu-mba.html", user=session.get('username'))

# ============ OTHER UNIVERSITY ROUTES (Coming Soon) ============

@app.route("/du")
@no_cache
def du():
    try:
        return render_template("du.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="University of Delhi (DU)", user=session.get('username'))

@app.route("/pu")
@no_cache
def pu():
    try:
        return render_template("pu.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Punjab University (PU)", user=session.get('username'))

@app.route("/jmi")
@no_cache
def jmi():
    try:
        return render_template("jmi.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Jamia Millia Islamia (JMI)", user=session.get('username'))

@app.route("/amu")
@no_cache
def amu():
    try:
        return render_template("amu.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Aligarh Muslim University (AMU)", user=session.get('username'))

@app.route("/bhu")
@no_cache
def bhu():
    try:
        return render_template("bhu.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Banaras Hindu University (BHU)", user=session.get('username'))

@app.route("/mumbai")
@no_cache
def mumbai():
    try:
        return render_template("mumbai.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="University of Mumbai", user=session.get('username'))

@app.route("/calcutta")
@no_cache
def calcutta():
    try:
        return render_template("calcutta.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Calcutta University (CU)", user=session.get('username'))

@app.route("/anna")
@no_cache
def anna():
    try:
        return render_template("anna.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Anna University", user=session.get('username'))

@app.route("/osmania")
@no_cache
def osmania():
    try:
        return render_template("osmania.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Osmania University", user=session.get('username'))

@app.route("/pune")
@no_cache
def pune():
    try:
        return render_template("pune.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Savitribai Phule Pune University", user=session.get('username'))

@app.route("/gujarat")
@no_cache
def gujarat():
    try:
        return render_template("gujarat.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Gujarat University", user=session.get('username'))

@app.route("/rajasthan")
@no_cache
def rajasthan():
    try:
        return render_template("rajasthan.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Rajasthan University (RU)", user=session.get('username'))

@app.route("/kurukshetra")
@no_cache
def kurukshetra():
    try:
        return render_template("kurukshetra.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Kurukshetra University", user=session.get('username'))

@app.route("/mdu")
@no_cache
def mdu():
    try:
        return render_template("mdu.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Maharshi Dayanand University (MDU)", user=session.get('username'))

@app.route("/ignou")
@no_cache
def ignou():
    try:
        return render_template("ignou.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="IGNOU", user=session.get('username'))

@app.route("/bangalore")
@no_cache
def bangalore():
    try:
        return render_template("bangalore.html", user=session.get('username'))
    except:
        return render_template("coming_soon.html", university_name="Bangalore University", user=session.get('username'))

# ============ API ENDPOINTS ============

@app.route("/api/universities")
@no_cache
def get_universities():
    universities_data = [
        {"name": "Indira Gandhi University (IGU)", "location": "Rewari, Haryana", "icon": "🏛️", "code": "igu", "available": True},
        {"name": "University of Delhi (DU)", "location": "Delhi", "icon": "📚", "code": "du", "available": False},
        {"name": "Punjab University (PU)", "location": "Chandigarh", "icon": "🎓", "code": "pu", "available": False},
        {"name": "Jamia Millia Islamia (JMI)", "location": "Delhi", "icon": "🏫", "code": "jmi", "available": False},
        {"name": "Aligarh Muslim University (AMU)", "location": "Aligarh, UP", "icon": "🌙", "code": "amu", "available": False},
        {"name": "Banaras Hindu University (BHU)", "location": "Varanasi, UP", "icon": "🕉️", "code": "bhu", "available": False},
        {"name": "University of Mumbai", "location": "Mumbai, MH", "icon": "🏝️", "code": "mumbai", "available": False},
        {"name": "Calcutta University (CU)", "location": "Kolkata, WB", "icon": "🎭", "code": "calcutta", "available": False},
        {"name": "Anna University", "location": "Chennai, TN", "icon": "⚙️", "code": "anna", "available": False},
        {"name": "Osmania University", "location": "Hyderabad, TS", "icon": "🌆", "code": "osmania", "available": False},
        {"name": "Savitribai Phule Pune University", "location": "Pune, MH", "icon": "📖", "code": "pune", "available": False},
        {"name": "Gujarat University", "location": "Ahmedabad, GJ", "icon": "🦁", "code": "gujarat", "available": False},
        {"name": "Rajasthan University (RU)", "location": "Jaipur, RJ", "icon": "🏜️", "code": "rajasthan", "available": False},
        {"name": "Kurukshetra University", "location": "Kurukshetra, HR", "icon": "⚔️", "code": "kurukshetra", "available": False},
        {"name": "Maharshi Dayanand University (MDU)", "location": "Rohtak, HR", "icon": "🧘", "code": "mdu", "available": False},
        {"name": "IGNOU", "location": "Delhi (Distance)", "icon": "📡", "code": "ignou", "available": False},
        {"name": "Bangalore University", "location": "Bengaluru, KA", "icon": "🌳", "code": "bangalore", "available": False}
    ]
    return jsonify(universities_data)

@app.route("/check_session")
@no_cache
def check_session():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'username': session.get('username'),
            'fullname': session.get('username'),
            'email': session.get('email')
        })
    return jsonify({'logged_in': False})

@app.route("/api/visitors")
@no_cache
def get_visitors():
    data = load_visitor_data()
    today = str(date.today())
    return jsonify({
        "today": data.get("daily", {}).get(today, 0),
        "week": get_weekly_total(data),
        "month": get_monthly_total(data),
        "total": data.get("total", 0)
    })

# ============ ADMIN ROUTES ============

@app.route("/admin", methods=["GET", "POST"])
@no_cache
def admin():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_panel"))
    
    if request.method == "POST":
        password = request.form.get("password")
        if password == app.config["ADMIN_PASSWORD"]:
            session["admin_logged_in"] = True
            flash("Admin login successful", "success")
            return redirect(url_for("admin_panel"))
        else:
            flash("Invalid admin password", "danger")
            return redirect(url_for("admin"))
    return render_template("admin_login.html")

@app.route("/admin/panel")
@admin_required
@no_cache
def admin_panel():
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return render_template("admin_panel.html", users=users)

@app.route("/admin/delete_user", methods=["POST"])
@admin_required
def admin_delete_user():
    user_id = request.form.get("user_id")
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        flash("User deleted successfully", "success")
    except Exception as e:
        flash(f"Error deleting user: {e}", "danger")
    return redirect(url_for("admin_panel"))

@app.route("/admin/forgot_user", methods=["POST"])
@admin_required
def admin_forgot_user():
    user_id = request.form.get("user_id")
    new_password = request.form.get("new_password", "").strip()
    
    if not new_password or len(new_password) < 6:
        flash("Password must be at least 6 characters", "danger")
        return redirect(url_for("admin_panel"))
    
    try:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user:
            hashed_password = generate_password_hash(new_password)
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id))
            conn.commit()
            flash(f"Password reset for {user['fullname']} successfully!", "success")
        else:
            flash("User not found", "danger")
        conn.close()
    except Exception as e:
        flash(f"Error resetting password: {e}", "danger")
    return redirect(url_for("admin_panel"))

@app.route("/admin/logout")
@no_cache
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Admin logged out successfully", "success")
    return redirect(url_for("home"))

# ============ COMING SOON TEMPLATE ROUTE ============
@app.route("/coming-soon")
def coming_soon():
    return render_template("coming_soon.html", university_name="Exam Saarthi")

# ============ STATIC FILE ROUTES ============
@app.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('static/images', filename)

@app.route('/static/icons/<path:filename>')
def serve_icon(filename):
    return send_from_directory('static/icons', filename)

# ============ ERROR HANDLERS ============
@app.errorhandler(404)
@no_cache
def page_not_found(e):
    return render_template("404.html", user=session.get('username')), 404

@app.errorhandler(500)
@no_cache
def internal_server_error(e):
    print(f"500 Error: {e}")
    flash("Something went wrong! Please try again later.", "danger")
    return redirect(url_for("home"))

# ============ RUN SERVER ============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("DEBUG", "False").lower() == "true"
    
    print("=" * 50)
    print("Exam Saarthi Server Starting...")
    print(f"Database: {DB_FILE}")
    print(f"Port: {port}")
    print(f"Secret Key: {'✓ Set' if app.secret_key else '✗ Missing'}")
    print("=" * 50)
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
