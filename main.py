from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import secrets

load_dotenv()

app = Flask(__name__)

# Set secret key with validation
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    # Generate a random secret key for development
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
    admin_password = "admin123"  # Default for development
    print("WARNING: No ADMIN_PASSWORD found in .env file! Using default: admin123")
    
app.config["ADMIN_PASSWORD"] = admin_password

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
        # Create new users table with full columns
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
        conn.close()
        print("Database created successfully!")
        return

    # If database exists, make sure all required columns exist
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

# Initialize DB
init_db()

# Home route
@app.route("/")
def home():
    return render_template("index.html")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully ✅", "success")
    return redirect(url_for("home"))

# Register route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Basic validation
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
            flash("User Registered Successfully! ✅", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError as e:
            if "email" in str(e).lower():
                flash("Email already exists ❌", "danger")
            else:
                flash("Username already exists ❌", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")

# Login route
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
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["fullname"] = user["fullname"]
            flash(f"Welcome back, {user['fullname']}! 🎉", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid Credentials ❌", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

# Other pages
@app.route("/university")
def university():
    return render_template("university.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

# Admin routes
@app.route("/admin", methods=["GET", "POST"])
def admin():
    # If already logged in as admin, redirect to panel
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
        # Handle delete user
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
        
        # Handle update user (optional)
        elif "update_user" in request.form:
            flash("Update feature coming soon ⚠️", "warning")
            return redirect(url_for("admin_panel"))
        
        else:
            flash("Invalid action ⚠️", "warning")
            return redirect(url_for("admin_panel"))

    return render_template("admin_panel.html", users=users)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Admin logged out successfully ✅", "success")
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)