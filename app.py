import os
import uuid
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from database import get_db, init_db
from models.grievance_model import classify, predict_priority, department_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
CATEGORIES = ["Academic", "Administrative", "Infrastructure", "Technical", "Examination", "Hostel", "Other"]
STATUSES = ["Pending", "In Progress", "Resolved", "Rejected"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "local-academic-demo-change-this-secret")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def user_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Administrator login is required.", "warning")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

def add_notification(conn, user_id, grievance_id, message):
    conn.execute(
        "INSERT INTO notifications(user_id,grievance_id,message) VALUES(?,?,?)",
        (user_id, grievance_id, message)
    )

def resolution_estimate(conn, grievance):
    """Estimate duration from resolved cases in the same category; fallback is explicitly demo-only."""
    if grievance is None:
        return None
    rows = conn.execute("""
        SELECT CAST((julianday(resolved_at)-julianday(created_at)) AS INTEGER) AS days
        FROM grievances
        WHERE category=? AND status='Resolved' AND resolved_at IS NOT NULL
          AND julianday(resolved_at)>=julianday(created_at)
        ORDER BY resolved_at DESC LIMIT 100
    """, (grievance["category"],)).fetchall()
    values = [max(0, int(row["days"])) for row in rows if row["days"] is not None]
    if len(values) >= 3:
        estimate = sorted(values)[len(values)//2]
        source = "Historical median for this category"
    else:
        estimate = {"Critical": 1, "High": 3, "Medium": 7, "Low": 10}.get(grievance["priority"], 7)
        source = "Demonstration fallback (not historical)"
    created = datetime.strptime(grievance["created_at"][:19], "%Y-%m-%d %H:%M:%S")
    return {"days": estimate, "date": (created + timedelta(days=estimate)).strftime("%d %b %Y"), "source": source}

@app.context_processor
def inject_globals():
    return {"current_user": session.get("user_name"), "is_admin": bool(session.get("admin_id"))}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        student_id = request.form.get("student_id", "").strip()
        department = request.form.get("department", "").strip()
        password = request.form.get("password", "")
        if not all([name, email, student_id, department, password]):
            flash("Please complete all fields.", "danger")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return render_template("register.html")
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users(full_name,email,student_id,department,password_hash) VALUES(?,?,?,?,?)",
                (name, email, student_id, department, generate_password_hash(password))
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("This email is already registered.", "danger")
            return render_template("register.html")
        conn.close()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            flash("Welcome back!", "success")
            return redirect(url_for("user_dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/submit", methods=["GET", "POST"])
@user_required
def submit_grievance():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        if not title or not description or category not in CATEGORIES:
            flash("Please enter a title, description, and valid category.", "danger")
            return render_template("submit_grievance.html", categories=CATEGORIES)
        predicted, confidence = classify(description)
        priority = predict_priority(title + " " + description)
        department = department_for(category)
        attachment_name = None
        upload = request.files.get("attachment")
        if upload and upload.filename:
            if not allowed_file(upload.filename):
                flash("Attachment must be PDF, PNG, JPG, or JPEG (maximum 5 MB).", "danger")
                return render_template("submit_grievance.html", categories=CATEGORIES)
            safe_name = secure_filename(upload.filename)
            attachment_name = f"{uuid.uuid4().hex}_{safe_name}"
            upload.save(os.path.join(UPLOAD_DIR, attachment_name))
        tracking_id = "GRV-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()
        conn = get_db()
        cur = conn.execute("""
            INSERT INTO grievances
            (tracking_id,user_id,title,description,category,predicted_category,category_confidence,
             priority,department,attachment)
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (tracking_id, session["user_id"], title, description, category, predicted,
              confidence, priority, department, attachment_name))
        grievance_id = cur.lastrowid
        add_notification(conn, session["user_id"], grievance_id,
                       f"Grievance {tracking_id} submitted successfully.")
        conn.commit()
        conn.close()
        flash(f"Grievance submitted successfully. Tracking ID: {tracking_id}", "success")
        return redirect(url_for("track_grievance", tracking_id=tracking_id))
    return render_template("submit_grievance.html", categories=CATEGORIES)

@app.route("/track", methods=["GET", "POST"])
def track_grievance():
    grievance = None
    tracking_id = request.values.get("tracking_id", "").strip()
    if tracking_id:
        conn = get_db()
        grievance = conn.execute("""
            SELECT g.*, u.full_name AS submitted_by
            FROM grievances g JOIN users u ON u.id=g.user_id
            WHERE g.tracking_id=?
        """, (tracking_id,)).fetchone()
        estimate = resolution_estimate(conn, grievance) if grievance else None
        conn.close()
        if not grievance:
            flash("No grievance found with that tracking ID.", "warning")
    else:
        estimate = None
    return render_template("track.html", grievance=grievance, tracking_id=tracking_id, estimate=estimate)

@app.route("/my-grievances")
@user_required
def user_dashboard():
    conn = get_db()
    grievances = conn.execute(
        "SELECT * FROM grievances WHERE user_id=? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 8",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("user_dashboard.html", grievances=grievances, notifications=notifications)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["username"]
            flash("Administrator authenticated.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid administrator credentials.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Administrator logged out.", "info")
    return redirect(url_for("index"))

@app.route("/admin")
@app.route("/dashboard")
@admin_required
def admin_dashboard():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    query = """SELECT g.*,u.full_name,u.email,u.student_id FROM grievances g
               JOIN users u ON u.id=g.user_id WHERE 1=1"""
    params = []
    if search:
        query += " AND (g.tracking_id LIKE ? OR g.title LIKE ? OR u.full_name LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    if status in STATUSES:
        query += " AND g.status=?"; params.append(status)
    if category in CATEGORIES:
        query += " AND g.category=?"; params.append(category)
    query += " ORDER BY g.created_at DESC LIMIT 250"
    conn = get_db()
    grievances = conn.execute(query, params).fetchall()
    stats = {
        "total": conn.execute("SELECT COUNT(*) FROM grievances").fetchone()[0],
        "pending": conn.execute("SELECT COUNT(*) FROM grievances WHERE status='Pending'").fetchone()[0],
        "progress": conn.execute("SELECT COUNT(*) FROM grievances WHERE status='In Progress'").fetchone()[0],
        "resolved": conn.execute("SELECT COUNT(*) FROM grievances WHERE status='Resolved'").fetchone()[0],
        "critical": conn.execute("SELECT COUNT(*) FROM grievances WHERE priority='Critical'").fetchone()[0],
    }
    category_stats = conn.execute("SELECT category,COUNT(*) count FROM grievances GROUP BY category").fetchall()
    status_stats = conn.execute("SELECT status,COUNT(*) count FROM grievances GROUP BY status").fetchall()
    priority_stats = conn.execute("SELECT priority,COUNT(*) count FROM grievances GROUP BY priority").fetchall()
    monthly_stats = conn.execute("""
       SELECT substr(created_at,1,7) month, COUNT(*) count
       FROM grievances GROUP BY substr(created_at,1,7) ORDER BY month DESC LIMIT 6
    """).fetchall()
    conn.close()
    return render_template("admin_dashboard.html", grievances=grievances, stats=stats,
        category_stats=category_stats, status_stats=status_stats,
        priority_stats=priority_stats, monthly_stats=monthly_stats,
        categories=CATEGORIES, statuses=STATUSES, search=search,
        selected_status=status, selected_category=category)

@app.route("/admin/grievance/<int:grievance_id>", methods=["GET", "POST"])
@admin_required
def grievance_details(grievance_id):
    conn = get_db()
    if request.method == "POST":
        status = request.form.get("status", "")
        priority = request.form.get("priority", "")
        department = request.form.get("department", "").strip()
        remarks = request.form.get("resolution_remarks", "").strip()
        if status not in STATUSES or priority not in PRIORITIES or not department:
            flash("Please provide valid status, priority, and department.", "danger")
        else:
            grievance = conn.execute("SELECT * FROM grievances WHERE id=?", (grievance_id,)).fetchone()
            if not grievance:
                conn.close(); abort(404)
            resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "Resolved" else None
            conn.execute("""
                UPDATE grievances SET status=?,priority=?,department=?,resolution_remarks=?,
                updated_at=CURRENT_TIMESTAMP,resolved_at=? WHERE id=?
            """, (status, priority, department, remarks, resolved_at, grievance_id))
            add_notification(conn, grievance["user_id"], grievance_id,
                           f"Your grievance {grievance['tracking_id']} status is now {status}.")
            conn.commit()
            flash("Grievance updated and user notification created.", "success")
            conn.close()
            return redirect(url_for("grievance_details", grievance_id=grievance_id))
    grievance = conn.execute("""
       SELECT g.*,u.full_name,u.email,u.student_id,u.department AS user_department
       FROM grievances g JOIN users u ON u.id=g.user_id WHERE g.id=?
    """, (grievance_id,)).fetchone()
    conn.close()
    if not grievance: abort(404)
    return render_template("grievance_details.html", grievance=grievance,
        statuses=STATUSES, priorities=PRIORITIES)

@app.errorhandler(413)
def too_large(_):
    flash("File is too large. Maximum upload size is 5 MB.", "danger")
    return redirect(url_for("submit_grievance"))

@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404

if __name__ == "__main__":
    init_db(
        os.environ.get("ADMIN_USERNAME", "admin"),
        os.environ.get("ADMIN_PASSWORD", "Admin@12345")
    )
    app.run(debug=True)
