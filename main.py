from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import secrets
from functools import wraps
from datetime import timedelta
import requests
import re

load_dotenv()

app = Flask(__name__)

# ============ SESSION CONFIGURATION ============
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Set secret key with validation
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    secret_key = secrets.token_hex(32)
    print("=" * 50)
    print("WARNING: No SECRET_KEY found in .env file!")
    print(f"Using generated key: {secret_key}")
    print("Add SECRET_KEY=your-secret-key to .env file for production")
    print("=" * 50)

app.secret_key = secret_key

# Set admin password with validation
admin_password = os.getenv("ADMIN_PASSWORD")
if not admin_password:
    admin_password = "admin123"
    print("WARNING: No ADMIN_PASSWORD found in .env file! Using default: admin123")
    
app.config["ADMIN_PASSWORD"] = admin_password

# ============ TELEGRAM BOT CONFIGURATION ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print("=" * 50)
print("Exam Saarthi - Telegram Bot Configuration")
if TELEGRAM_BOT_TOKEN:
    print(f"[OK] Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...")
else:
    print("[ERROR] Bot Token: Not Found")
    
if TELEGRAM_CHAT_ID:
    print(f"[OK] Chat ID: {TELEGRAM_CHAT_ID}")
else:
    print("[ERROR] Chat ID: Not Found")
print("=" * 50)

DB_FILE = "database.db"

# Database connection
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database
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
            password TEXT NOT NULL
        )
        """)
        conn.commit()
        print("Database created successfully!")
    else:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN fullname TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN mobile TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT UNIQUE")
        except sqlite3.OperationalError:
            pass
        conn.commit()
    
    conn.close()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page 🔒', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize DB
init_db()

# ============ TELEGRAM MESSAGE FUNCTION ============
def send_telegram_message(name, email, university, course, message):
    """Send message to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured")
        return False
    
    # Format message (without markdown to avoid issues)
    msg = f"""
*NEW CONTACT FORM SUBMISSION*

Name: {name}
Email: {email}
University: {university}
Course: {course if course else 'Not specified'}

Message:
{message}

---
Time: {__import__('datetime').datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
Source: Exam Saarthi Website
    """
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"Telegram message sent successfully for {name}")
            return True
        else:
            print(f"Telegram error: {response.text}")
            return False
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# ============ CONTACT FORM HANDLER ============
@app.route("/submit_contact", methods=["POST"])
def submit_contact():
    """Handle contact form submission and send to Telegram"""
    try:
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        university = request.form.get("university", "").strip()
        course = request.form.get("course", "").strip()
        message = request.form.get("message", "").strip()

        # Validation
        if not name or not email or not university or not message:
            return jsonify({"success": False, "message": "Please fill all required fields"})

        # Email validation
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, email):
            return jsonify({"success": False, "message": "Please enter a valid email address"})

        # Send to Telegram
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            success = send_telegram_message(name, email, university, course, message)
            if success:
                print(f"Message sent to Telegram for {name}")
                return jsonify({"success": True, "message": "Message sent successfully! We'll get back to you soon."})
            else:
                print(f"Failed to send Telegram message for {name}")
                return jsonify({"success": False, "message": "Failed to send message. Please try again."})
        else:
            # Log the message if Telegram not configured
            print(f"Contact Form Submission (Telegram not configured):")
            print(f"Name: {name}")
            print(f"Email: {email}")
            print(f"University: {university}")
            print(f"Message: {message}")
            return jsonify({"success": True, "message": "Message received! (Demo mode - Telegram not configured)"})

    except Exception as e:
        print(f"Error in contact form: {e}")
        return jsonify({"success": False, "message": "An error occurred. Please try again."})

# ============ TEST TELEGRAM ROUTE ============
@app.route("/test-telegram")
def test_telegram():
    """Test Telegram bot connection"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return jsonify({"success": False, "message": "Telegram not configured"})
    
    test_msg = send_telegram_message("Test User", "test@example.com", "Test University", "Test Course", "This is a test message from Exam Saarthi")
    
    if test_msg:
        return jsonify({"success": True, "message": "Test message sent to Telegram!"})
    else:
        return jsonify({"success": False, "message": "Failed to send test message"})

# ============ MAIN ROUTES ============

@app.route("/")
def home():
    return render_template("index.html", user=session.get('fullname'))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([fullname, mobile, email, username, password]):
            flash("All fields are required ❌", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match ❌", "danger")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters ❌", "danger")
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
            flash("User Registered Successfully! ✅ Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError as e:
            if "email" in str(e).lower():
                flash("Email already exists ❌", "danger")
            else:
                flash("Username already exists ❌", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username_email = request.form.get("username_email", "").strip()
        password = request.form.get("password", "")

        if not username_email or not password:
            flash("Please enter both username/email and password ❌", "danger")
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
            
            flash(f"Welcome back, {user['fullname']}! 🎉", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid Credentials ❌", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully ✅", "success")
    return redirect(url_for("home"))

# ============ PROTECTED ROUTES ============

@app.route("/university")
@login_required
def university():
    return render_template("university.html", user=session.get('fullname'))

@app.route("/about")
def about():
    return render_template("about.html", user=session.get('fullname'))

@app.route("/contact")
def contact():
    return render_template("contact.html", user=session.get('fullname'))

# ============ IGU UNIVERSITY ROUTES ============

@app.route("/igu")
def igu():
    return render_template("igu.html", user=session.get('fullname'))

@app.route("/igu-btech")
def igu_btech():
    return render_template("igu-btech.html", user=session.get('fullname'))

@app.route("/igu-mtech")
def igu_mtech():
    return render_template("igu-mtech.html", user=session.get('fullname'))

@app.route("/igu-bca")
def igu_bca():
    return render_template("igu-bca.html", user=session.get('fullname'))

@app.route("/igu-bba")
def igu_bba():
    return render_template("igu-bba.html", user=session.get('fullname'))

@app.route("/igu-bsc")
def igu_bsc():
    return render_template("igu-bsc.html", user=session.get('fullname'))

@app.route("/igu-msc")
def igu_msc():
    return render_template("igu-msc.html", user=session.get('fullname'))

@app.route("/igu-ba")
def igu_ba():
    return render_template("igu-ba.html", user=session.get('fullname'))

@app.route("/igu-ma")
def igu_ma():
    return render_template("igu-ma.html", user=session.get('fullname'))

@app.route("/igu-bcom")
def igu_bcom():
    return render_template("igu-bcom.html", user=session.get('fullname'))

@app.route("/igu-mcom")
def igu_mcom():
    return render_template("igu-mcom.html", user=session.get('fullname'))

@app.route("/igu-bed")
def igu_bed():
    return render_template("igu-bed.html", user=session.get('fullname'))

@app.route("/igu-llb")
def igu_llb():
    return render_template("igu-llb.html", user=session.get('fullname'))

@app.route("/igu-mca")
def igu_mca():
    return render_template("igu-mca.html", user=session.get('fullname'))

@app.route("/igu-mba")
def igu_mba():
    return render_template("igu-mba.html", user=session.get('fullname'))

# ============ OTHER UNIVERSITY ROUTES ============

@app.route("/du")
def du():
    return render_template("du.html", user=session.get('fullname'))

@app.route("/pu")
def pu():
    return render_template("pu.html", user=session.get('fullname'))

@app.route("/jmi")
def jmi():
    return render_template("jmi.html", user=session.get('fullname'))

@app.route("/amu")
def amu():
    return render_template("amu.html", user=session.get('fullname'))

@app.route("/bhu")
def bhu():
    return render_template("bhu.html", user=session.get('fullname'))

@app.route("/mumbai")
def mumbai():
    return render_template("mumbai.html", user=session.get('fullname'))

@app.route("/calcutta")
def calcutta():
    return render_template("calcutta.html", user=session.get('fullname'))

@app.route("/anna")
def anna():
    return render_template("anna.html", user=session.get('fullname'))

@app.route("/osmania")
def osmania():
    return render_template("osmania.html", user=session.get('fullname'))

@app.route("/pune")
def pune():
    return render_template("pune.html", user=session.get('fullname'))

@app.route("/gujarat")
def gujarat():
    return render_template("gujarat.html", user=session.get('fullname'))

@app.route("/rajasthan")
def rajasthan():
    return render_template("rajasthan.html", user=session.get('fullname'))

@app.route("/kurukshetra")
def kurukshetra():
    return render_template("kurukshetra.html", user=session.get('fullname'))

@app.route("/mdu")
def mdu():
    return render_template("mdu.html", user=session.get('fullname'))

@app.route("/ignou")
def ignou():
    return render_template("ignou.html", user=session.get('fullname'))

@app.route("/bangalore")
def bangalore():
    return render_template("bangalore.html", user=session.get('fullname'))

# ============ API ENDPOINTS ============

@app.route("/check_session")
def check_session():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'username': session.get('username'),
            'fullname': session.get('fullname'),
            'email': session.get('email')
        })
    return jsonify({'logged_in': False})

@app.route("/api/universities")
def get_universities():
    universities_data = [
        {"name": "Indira Gandhi University (IGU)", "location": "Rewari, Haryana", "icon": "🏛️", "code": "igu"},
        {"name": "University of Delhi (DU)", "location": "Delhi", "icon": "📚", "code": "du"},
        {"name": "Punjab University (PU)", "location": "Chandigarh", "icon": "🎓", "code": "pu"},
        {"name": "Jamia Millia Islamia (JMI)", "location": "Delhi", "icon": "🏫", "code": "jmi"},
        {"name": "Aligarh Muslim University (AMU)", "location": "Aligarh, UP", "icon": "🌙", "code": "amu"},
        {"name": "Banaras Hindu University (BHU)", "location": "Varanasi, UP", "icon": "🕉️", "code": "bhu"},
        {"name": "University of Mumbai", "location": "Mumbai, MH", "icon": "🏝️", "code": "mumbai"},
        {"name": "Calcutta University (CU)", "location": "Kolkata, WB", "icon": "🎭", "code": "calcutta"},
        {"name": "Anna University", "location": "Chennai, TN", "icon": "⚙️", "code": "anna"},
        {"name": "Osmania University", "location": "Hyderabad, TS", "icon": "🌆", "code": "osmania"},
        {"name": "Savitribai Phule Pune University", "location": "Pune, MH", "icon": "📖", "code": "pune"},
        {"name": "Gujarat University", "location": "Ahmedabad, GJ", "icon": "🦁", "code": "gujarat"},
        {"name": "Rajasthan University (RU)", "location": "Jaipur, RJ", "icon": "🏜️", "code": "rajasthan"},
        {"name": "Kurukshetra University", "location": "Kurukshetra, HR", "icon": "⚔️", "code": "kurukshetra"},
        {"name": "Maharshi Dayanand University (MDU)", "location": "Rohtak, HR", "icon": "🧘", "code": "mdu"},
        {"name": "IGNOU", "location": "Delhi (Distance)", "icon": "📡", "code": "ignou"},
        {"name": "Bangalore University", "location": "Bengaluru, KA", "icon": "🌳", "code": "bangalore"}
    ]
    return jsonify(universities_data)

# ============ ADMIN ROUTES ============

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_panel"))
    
    if request.method == "POST":
        password = request.form.get("password")
        if password == app.config["ADMIN_PASSWORD"]:
            session["admin_logged_in"] = True
            flash("Admin login successful ✅", "success")
            return redirect(url_for("admin_panel"))
        else:
            flash("Invalid admin password ❌", "danger")
            return redirect(url_for("admin"))
    return render_template("admin_login.html")

@app.route("/admin/panel", methods=["GET", "POST"])
def admin_panel():
    if not session.get("admin_logged_in"):
        flash("Please login as admin first ❌", "danger")
        return redirect(url_for("admin"))

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()

    if request.method == "POST":
        if "delete_user" in request.form:
            user_id = request.form.get("user_id")
            try:
                conn = get_db_connection()
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                conn.close()
                flash("User deleted successfully ✅", "success")
            except Exception as e:
                flash(f"Error deleting user: {e}", "danger")
            return redirect(url_for("admin_panel"))

    return render_template("admin_panel.html", users=users)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Admin logged out successfully ✅", "success")
    return redirect(url_for("home"))

if __name__ == "__main__":
    print("=" * 50)
    print("Exam Saarthi Server Starting...")
    print(f"Database: {DB_FILE}")
    print(f"Admin Password: {'*' * len(app.config['ADMIN_PASSWORD'])}")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("Telegram Bot: Configured [OK]")
        print("Messages will be sent to your Telegram")
    else:
        print("Telegram Bot: Not Configured [X]")
        print("Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env file")
    print("=" * 50)
    print("Server running at: http://127.0.0.1:5000")
    print("Test Telegram: http://127.0.0.1:5000/test-telegram")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
