from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import secrets
from functools import wraps
from datetime import timedelta
import requests

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

# ============ WEB3FORMS API KEY ============
web3forms_key = os.getenv("WEB3FORMS_ACCESS_KEY")
if not web3forms_key:
    web3forms_key = ""
    print("=" * 50)
    print("WARNING: No WEB3FORMS_ACCESS_KEY found in .env file!")
    print("Contact form will not work without it.")
    print("Get your free key from: https://web3forms.com/")
    print("Add WEB3FORMS_ACCESS_KEY=your-key-here to .env file")
    print("=" * 50)
else:
    print("=" * 50)
    print(f"Web3Forms API Key loaded")
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

# ============ CONTACT FORM HANDLER (BACKEND) ============

@app.route("/submit_contact", methods=["POST"])
def submit_contact():
    """Handle contact form submission via backend"""
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
        import re
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, email):
            return jsonify({"success": False, "message": "Please enter a valid email address"})

        # Check if Web3Forms key is configured
        if not web3forms_key:
            return jsonify({"success": False, "message": "Contact form is not configured. Please contact administrator."})

        # Send to Web3Forms API
        form_data = {
            "access_key": web3forms_key,
            "name": name,
            "email": email,
            "university": university,
            "course": course,
            "message": message,
            "subject": f"Query from {name} - {university}"
        }

        response = requests.post("https://api.web3forms.com/submit", data=form_data)
        result = response.json()

        if result.get("success"):
            return jsonify({"success": True, "message": "Message sent successfully!"})
        else:
            return jsonify({"success": False, "message": result.get("message", "Failed to send message")})

    except Exception as e:
        print(f"Error in contact form: {e}")
        return jsonify({"success": False, "message": "An error occurred. Please try again."})

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

@app.route("/madras")
def madras():
    return render_template("madras.html", user=session.get('fullname'))

@app.route("/kerala")
def kerala():
    return render_template("kerala.html", user=session.get('fullname'))

@app.route("/andhra")
def andhra():
    return render_template("andhra.html", user=session.get('fullname'))

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
    if web3forms_key:
        print("Web3Forms API Key: Loaded (Hidden from frontend)")
    else:
        print("Web3Forms API Key: Not Found")
    print("=" * 50)
    print("Server running at: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
