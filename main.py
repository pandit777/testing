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
    """Handle contact form submission - PUBLIC (so anyone can contact)"""
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
            print(f"Contact Form Submission (Telegram not configured):")
            print(f"Name: {name}")
            print(f"Email: {email}")
            print(f"University: {university}")
            print(f"Message: {message}")
            return jsonify({"success": True, "message": "Message received! (Demo mode - Telegram not configured)"})

    except Exception as e:
        print(f"Error in contact form: {e}")
        return jsonify({"success": False, "message": "An error occurred. Please try again."})

# ============ MAIN ROUTES ============

@app.route("/")
def home():
    """Home page - requires login"""
    return render_template("index.html", user=session.get('fullname'))

@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration page - PUBLIC (so new users can sign up)"""
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
    """User login page - PUBLIC"""
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
    """User logout - PUBLIC"""
    session.clear()
    flash("Logged out successfully ✅", "success")
    return redirect(url_for("login"))

# ============ PUBLIC ROUTES (No Login Required) ============

@app.route("/about")
def about():
    """About page - PUBLIC (no login required)"""
    return render_template("about.html", user=session.get('fullname'))

@app.route("/contact")
def contact():
    """Contact page - PUBLIC (no login required)"""
    return render_template("contact.html", user=session.get('fullname'))

# ============ PROTECTED ROUTES (Login Required) ============

@app.route("/university")
@login_required
def university():
    """Universities page - requires login"""
    return render_template("university.html", user=session.get('fullname'))

# ============ IGU UNIVERSITY ROUTES (ALL PROTECTED) ============

@app.route("/igu")
@login_required
def igu():
    """IGU University Main Page - requires login"""
    return render_template("igu.html", user=session.get('fullname'))

@app.route("/igu-btech")
@login_required
def igu_btech():
    """IGU B.Tech Page - requires login"""
    return render_template("igu-btech.html", user=session.get('fullname'))

@app.route("/igu-mtech")
@login_required
def igu_mtech():
    """IGU M.Tech Page - requires login"""
    return render_template("igu-mtech.html", user=session.get('fullname'))

@app.route("/igu-bca")
@login_required
def igu_bca():
    """IGU BCA Page - requires login"""
    return render_template("igu-bca.html", user=session.get('fullname'))

@app.route("/igu-bba")
@login_required
def igu_bba():
    """IGU BBA Page - requires login"""
    return render_template("igu-bba.html", user=session.get('fullname'))

@app.route("/igu-bsc")
@login_required
def igu_bsc():
    """IGU B.Sc Page - requires login"""
    return render_template("igu-bsc.html", user=session.get('fullname'))

@app.route("/igu-msc")
@login_required
def igu_msc():
    """IGU M.Sc Page - requires login"""
    return render_template("igu-msc.html", user=session.get('fullname'))

@app.route("/igu-ba")
@login_required
def igu_ba():
    """IGU BA Page - requires login"""
    return render_template("igu-ba.html", user=session.get('fullname'))

@app.route("/igu-ma")
@login_required
def igu_ma():
    """IGU MA Page - requires login"""
    return render_template("igu-ma.html", user=session.get('fullname'))

@app.route("/igu-bcom")
@login_required
def igu_bcom():
    """IGU B.Com Page - requires login"""
    return render_template("igu-bcom.html", user=session.get('fullname'))

@app.route("/igu-mcom")
@login_required
def igu_mcom():
    """IGU M.Com Page - requires login"""
    return render_template("igu-mcom.html", user=session.get('fullname'))

@app.route("/igu-bed")
@login_required
def igu_bed():
    """IGU B.Ed Page - requires login"""
    return render_template("igu-bed.html", user=session.get('fullname'))

@app.route("/igu-llb")
@login_required
def igu_llb():
    """IGU LLB Page - requires login"""
    return render_template("igu-llb.html", user=session.get('fullname'))

@app.route("/igu-mca")
@login_required
def igu_mca():
    """IGU MCA Page - requires login"""
    return render_template("igu-mca.html", user=session.get('fullname'))

@app.route("/igu-mba")
@login_required
def igu_mba():
    """IGU MBA Page - requires login"""
    return render_template("igu-mba.html", user=session.get('fullname'))

# ============ OTHER UNIVERSITY ROUTES (ALL PROTECTED) ============

@app.route("/du")
@login_required
def du():
    """Delhi University Page - requires login"""
    return render_template("du.html", user=session.get('fullname'))

@app.route("/pu")
@login_required
def pu():
    """Punjab University Page - requires login"""
    return render_template("pu.html", user=session.get('fullname'))

@app.route("/jmi")
@login_required
def jmi():
    """Jamia Millia Islamia Page - requires login"""
    return render_template("jmi.html", user=session.get('fullname'))

@app.route("/amu")
@login_required
def amu():
    """Aligarh Muslim University Page - requires login"""
    return render_template("amu.html", user=session.get('fullname'))

@app.route("/bhu")
@login_required
def bhu():
    """Banaras Hindu University Page - requires login"""
    return render_template("bhu.html", user=session.get('fullname'))

@app.route("/mumbai")
@login_required
def mumbai():
    """University of Mumbai Page - requires login"""
    return render_template("mumbai.html", user=session.get('fullname'))

@app.route("/calcutta")
@login_required
def calcutta():
    """Calcutta University Page - requires login"""
    return render_template("calcutta.html", user=session.get('fullname'))

@app.route("/anna")
@login_required
def anna():
    """Anna University Page - requires login"""
    return render_template("anna.html", user=session.get('fullname'))

@app.route("/osmania")
@login_required
def osmania():
    """Osmania University Page - requires login"""
    return render_template("osmania.html", user=session.get('fullname'))

@app.route("/pune")
@login_required
def pune():
    """Savitribai Phule Pune University Page - requires login"""
    return render_template("pune.html", user=session.get('fullname'))

@app.route("/gujarat")
@login_required
def gujarat():
    """Gujarat University Page - requires login"""
    return render_template("gujarat.html", user=session.get('fullname'))

@app.route("/rajasthan")
@login_required
def rajasthan():
    """Rajasthan University Page - requires login"""
    return render_template("rajasthan.html", user=session.get('fullname'))

@app.route("/kurukshetra")
@login_required
def kurukshetra():
    """Kurukshetra University Page - requires login"""
    return render_template("kurukshetra.html", user=session.get('fullname'))

@app.route("/mdu")
@login_required
def mdu():
    """Maharshi Dayanand University Page - requires login"""
    return render_template("mdu.html", user=session.get('fullname'))

@app.route("/ignou")
@login_required
def ignou():
    """IGNOU Page - requires login"""
    return render_template("ignou.html", user=session.get('fullname'))

@app.route("/bangalore")
@login_required
def bangalore():
    """Bangalore University Page - requires login"""
    return render_template("bangalore.html", user=session.get('fullname'))

# ============ API ENDPOINTS ============

@app.route("/check_session")
def check_session():
    """Check if user is logged in (for AJAX calls) - PUBLIC"""
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'username': session.get('username'),
            'fullname': session.get('fullname'),
            'email': session.get('email')
        })
    return jsonify({'logged_in': False})

@app.route("/api/universities")
@login_required
def get_universities():
    """Get list of universities - requires login"""
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
    """Admin login page - PUBLIC"""
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

@app.route("/admin/panel")
@login_required
def admin_panel():
    """Admin panel - requires both admin login and user login"""
    if not session.get("admin_logged_in"):
        flash("Please login as admin first ❌", "danger")
        return redirect(url_for("admin"))

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()

    return render_template("admin_panel.html", users=users)

@app.route("/admin/delete_user", methods=["POST"])
@login_required
def admin_delete_user():
    """Delete user - admin only"""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Admin access required"})
    
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

@app.route("/admin/logout")
def admin_logout():
    """Admin logout"""
    session.pop("admin_logged_in", None)
    flash("Admin logged out successfully ✅", "success")
    return redirect(url_for("login"))

if __name__ == "__main__":
    print("=" * 50)
    print("Exam Saarthi Server Starting...")
    print(f"Database: {DB_FILE}")
    print(f"Admin Password: {'*' * len(app.config['ADMIN_PASSWORD'])}")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("Telegram Bot: Configured [OK]")
    else:
        print("Telegram Bot: Not Configured [X]")
    print("=" * 50)
    print("ACCESS RULES:")
    print("- Home Page: Login Required")
    print("- Universities: Login Required")
    print("- IGU Pages: Login Required")
    print("- All University Pages: Login Required")
    print("- About: Public (No Login Required)")
    print("- Contact: Public (No Login Required)")
    print("- Register: Public")
    print("- Login: Public")
    print("=" * 50)
    print("Server running at: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
