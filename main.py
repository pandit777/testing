from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import secrets
from functools import wraps
from datetime import timedelta
import requests
import re
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl

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

# ============ EMAIL CONFIGURATION ============
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

print("=" * 50)
print("Exam Saarthi - Configuration")
if EMAIL_USER and EMAIL_PASSWORD:
    print(f"[OK] Email: {EMAIL_USER}")
else:
    print("[WARNING] Email not configured. Forgot password will not work.")
    print("Add EMAIL_USER and EMAIL_PASSWORD to .env file")
    print("Get App Password from: https://myaccount.google.com/apppasswords")

# ============ TELEGRAM BOT CONFIGURATION ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    print(f"[OK] Telegram Bot: Configured")
else:
    print("[WARNING] Telegram Bot: Not Configured")
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
        try:
            conn.execute("""
            CREATE TABLE reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                token TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
        except sqlite3.OperationalError:
            pass
        conn.commit()
    
    conn.close()

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

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize DB
init_db()

# ============ EMAIL SENDING FUNCTION ============
def send_reset_email(to_email, token):
    """Send password reset email with token"""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("Email not configured")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = "Exam Saarthi - Password Reset Request"
        
        # Email body
        body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .token {{ background: #e3f2fd; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 20px; text-align: center; margin: 20px 0; letter-spacing: 2px; }}
                .btn {{ background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #999; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Exam Saarthi</h2>
                    <p>Password Reset Request</p>
                </div>
                <div class="content">
                    <p>Hello,</p>
                    <p>We received a request to reset your password for your Exam Saarthi account.</p>
                    <p>Use the following token to reset your password:</p>
                    <div class="token">
                        <strong>{token}</strong>
                    </div>
                    <p style="text-align: center;">
                        <a href="http://127.0.0.1:5000/reset-password" class="btn">Reset Password</a>
                    </p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p>http://127.0.0.1:5000/reset-password</p>
                    <p><strong>This token will expire in 1 hour.</strong></p>
                    <p>If you didn't request this, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2025 Exam Saarthi. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email using Gmail SMTP
        context = ssl.create_default_context()
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls(context=context)
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"[OK] Reset email sent to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[ERROR] Authentication failed: {e}")
        print("Troubleshooting:")
        print("1. Make sure you're using App Password, not regular password")
        print("2. Generate App Password: https://myaccount.google.com/apppasswords")
        print("3. Select 'Mail' and 'Other (Custom name)'")
        return False
    except Exception as e:
        print(f"[ERROR] Email error: {e}")
        return False

# ============ RESET TOKEN FUNCTIONS ============
def generate_reset_token():
    """Generate random reset token"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def save_reset_token(email, token):
    """Save reset token to database"""
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
    """Verify reset token"""
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
    """Delete reset token after use"""
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM reset_tokens WHERE email = ?", (email,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error deleting token: {e}")

# ============ TELEGRAM MESSAGE FUNCTION ============
def send_telegram_message(name, email, university, course, message):
    """Send message to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
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
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

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

        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            success = send_telegram_message(name, email, university, course, message)
            if success:
                return jsonify({"success": True, "message": "Message sent successfully! We'll get back to you soon."})
            else:
                return jsonify({"success": False, "message": "Failed to send message. Please try again."})
        else:
            return jsonify({"success": True, "message": "Message received! (Demo mode)"})

    except Exception as e:
        print(f"Error in contact form: {e}")
        return jsonify({"success": False, "message": "An error occurred. Please try again."})

# ============ FORGOT PASSWORD ROUTES ============

@app.route("/forgot-password", methods=["GET", "POST"])
@no_cache
def forgot_password():
    """Forgot password page - sends email with token"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        if not email:
            flash("Please enter your email address", "danger")
            return redirect(url_for("forgot_password"))
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        if user:
            token = generate_reset_token()
            
            if save_reset_token(email, token):
                if send_reset_email(email, token):
                    flash(f"Password reset email sent to {email}! Check your inbox.", "success")
                    session['reset_email'] = email
                    return redirect(url_for("reset_password"))
                else:
                    flash("Failed to send email. Please try again.", "danger")
            else:
                flash("Failed to generate reset token. Please try again.", "danger")
        else:
            flash("Email not found", "danger")
            return redirect(url_for("forgot_password"))
    
    return render_template("forgot_password.html")

@app.route("/reset-password", methods=["GET", "POST"])
@no_cache
def reset_password():
    """Reset password page - verify token and reset password"""
    if request.method == "POST":
        token = request.form.get("token", "").strip().upper()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        email = session.get('reset_email')
        
        if not email:
            flash("Session expired. Please request password reset again.", "danger")
            return redirect(url_for("forgot_password"))
        
        if not token or not new_password:
            flash("Please enter token and new password", "danger")
            return redirect(url_for("reset_password"))
        
        if new_password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("reset_password"))
        
        if len(new_password) < 6:
            flash("Password must be at least 6 characters", "danger")
            return redirect(url_for("reset_password"))
        
        if verify_reset_token(email, token):
            hashed_password = generate_password_hash(new_password)
            
            try:
                conn = get_db_connection()
                conn.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
                conn.commit()
                conn.close()
                
                delete_reset_token(email)
                session.pop('reset_email', None)
                
                flash("Password reset successfully! Please login with new password.", "success")
                return redirect(url_for("login"))
            except Exception as e:
                flash(f"Error resetting password: {e}", "danger")
                return redirect(url_for("reset_password"))
        else:
            flash("Invalid or expired token", "danger")
            return redirect(url_for("reset_password"))
    
    return render_template("reset_password.html")

# ============ MAIN ROUTES ============

@app.route("/")
@no_cache
def home():
    return render_template("index.html", user=session.get('fullname'))

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
    try:
        user_name = session.get('fullname', 'User')
        session.clear()
        flash(f"Goodbye, {user_name}! You have been logged out successfully.", "success")
        response = make_response(redirect(url_for("login")))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
    except Exception as e:
        print(f"Logout error: {e}")
        session.clear()
        response = make_response(redirect(url_for("login")))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

# ============ PUBLIC ROUTES ============

@app.route("/about")
@no_cache
def about():
    return render_template("about.html", user=session.get('fullname'))

@app.route("/contact")
@no_cache
def contact():
    return render_template("contact.html", user=session.get('fullname'))

# ============ PROTECTED ROUTES ============

@app.route("/university")
@login_required
@no_cache
def university():
    return render_template("university.html", user=session.get('fullname'))

# ============ IGU ROUTES ============
@app.route("/igu")
@login_required
@no_cache
def igu():
    return render_template("igu.html", user=session.get('fullname'))

@app.route("/igu-btech")
@login_required
@no_cache
def igu_btech():
    return render_template("igu-btech.html", user=session.get('fullname'))

@app.route("/igu-mtech")
@login_required
@no_cache
def igu_mtech():
    return render_template("igu-mtech.html", user=session.get('fullname'))

@app.route("/igu-bca")
@login_required
@no_cache
def igu_bca():
    return render_template("igu-bca.html", user=session.get('fullname'))

@app.route("/igu-bba")
@login_required
@no_cache
def igu_bba():
    return render_template("igu-bba.html", user=session.get('fullname'))

@app.route("/igu-bsc")
@login_required
@no_cache
def igu_bsc():
    return render_template("igu-bsc.html", user=session.get('fullname'))

@app.route("/igu-msc")
@login_required
@no_cache
def igu_msc():
    return render_template("igu-msc.html", user=session.get('fullname'))

@app.route("/igu-ba")
@login_required
@no_cache
def igu_ba():
    return render_template("igu-ba.html", user=session.get('fullname'))

@app.route("/igu-ma")
@login_required
@no_cache
def igu_ma():
    return render_template("igu-ma.html", user=session.get('fullname'))

@app.route("/igu-bcom")
@login_required
@no_cache
def igu_bcom():
    return render_template("igu-bcom.html", user=session.get('fullname'))

@app.route("/igu-mcom")
@login_required
@no_cache
def igu_mcom():
    return render_template("igu-mcom.html", user=session.get('fullname'))

@app.route("/igu-bed")
@login_required
@no_cache
def igu_bed():
    return render_template("igu-bed.html", user=session.get('fullname'))

@app.route("/igu-llb")
@login_required
@no_cache
def igu_llb():
    return render_template("igu-llb.html", user=session.get('fullname'))

@app.route("/igu-mca")
@login_required
@no_cache
def igu_mca():
    return render_template("igu-mca.html", user=session.get('fullname'))

@app.route("/igu-mba")
@login_required
@no_cache
def igu_mba():
    return render_template("igu-mba.html", user=session.get('fullname'))

# ============ OTHER UNIVERSITY ROUTES ============
@app.route("/du")
@login_required
@no_cache
def du():
    return render_template("du.html", user=session.get('fullname'))

@app.route("/pu")
@login_required
@no_cache
def pu():
    return render_template("pu.html", user=session.get('fullname'))

@app.route("/jmi")
@login_required
@no_cache
def jmi():
    return render_template("jmi.html", user=session.get('fullname'))

@app.route("/amu")
@login_required
@no_cache
def amu():
    return render_template("amu.html", user=session.get('fullname'))

@app.route("/bhu")
@login_required
@no_cache
def bhu():
    return render_template("bhu.html", user=session.get('fullname'))

@app.route("/mumbai")
@login_required
@no_cache
def mumbai():
    return render_template("mumbai.html", user=session.get('fullname'))

@app.route("/calcutta")
@login_required
@no_cache
def calcutta():
    return render_template("calcutta.html", user=session.get('fullname'))

@app.route("/anna")
@login_required
@no_cache
def anna():
    return render_template("anna.html", user=session.get('fullname'))

@app.route("/osmania")
@login_required
@no_cache
def osmania():
    return render_template("osmania.html", user=session.get('fullname'))

@app.route("/pune")
@login_required
@no_cache
def pune():
    return render_template("pune.html", user=session.get('fullname'))

@app.route("/gujarat")
@login_required
@no_cache
def gujarat():
    return render_template("gujarat.html", user=session.get('fullname'))

@app.route("/rajasthan")
@login_required
@no_cache
def rajasthan():
    return render_template("rajasthan.html", user=session.get('fullname'))

@app.route("/kurukshetra")
@login_required
@no_cache
def kurukshetra():
    return render_template("kurukshetra.html", user=session.get('fullname'))

@app.route("/mdu")
@login_required
@no_cache
def mdu():
    return render_template("mdu.html", user=session.get('fullname'))

@app.route("/ignou")
@login_required
@no_cache
def ignou():
    return render_template("ignou.html", user=session.get('fullname'))

@app.route("/bangalore")
@login_required
@no_cache
def bangalore():
    return render_template("bangalore.html", user=session.get('fullname'))

# ============ API ENDPOINTS ============

@app.route("/check_session")
@no_cache
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
@login_required
@no_cache
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
@no_cache
def admin_panel():
    if not session.get("admin_logged_in"):
        flash("Please login as admin first", "danger")
        return redirect(url_for("admin"))

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()

    return render_template("admin_panel.html", users=users)

@app.route("/admin/delete_user", methods=["POST"])
def admin_delete_user():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Admin access required"})
    
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
def admin_forgot_user():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Admin access required"})
    
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
    response = make_response(redirect(url_for("login")))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ============ ERROR HANDLERS ============

@app.errorhandler(404)
@no_cache
def page_not_found(e):
    return render_template("404.html", user=session.get('fullname')), 404

@app.errorhandler(500)
@no_cache
def internal_server_error(e):
    print(f"500 Error: {e}")
    flash("Something went wrong! Please try again later.", "danger")
    return redirect(url_for("home"))

if __name__ == "__main__":
    print("=" * 50)
    print("Exam Saarthi Server Starting...")
    print(f"Database: {DB_FILE}")
    print(f"Admin Password: {'*' * len(app.config['ADMIN_PASSWORD'])}")
    if EMAIL_USER and EMAIL_PASSWORD:
        print(f"Email: Configured ({EMAIL_USER})")
    else:
        print("Email: Not Configured")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("Telegram Bot: Configured")
    else:
        print("Telegram Bot: Not Configured")
    print("=" * 50)
    print("ACCESS RULES:")
    print("- Home Page: Public")
    print("- Universities: Login Required")
    print("- All University Pages: Login Required")
    print("- About: Public")
    print("- Contact: Public")
    print("- Register: Public")
    print("- Login: Public")
    print("- Forgot Password: Public (Email Required)")
    print("=" * 50)
    print("Server running at: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
