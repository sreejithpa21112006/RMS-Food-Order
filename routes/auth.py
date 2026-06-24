from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from firebase_admin import auth as firebase_auth
import mysql.connector
from functools import wraps
from database import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.before_app_request
def require_login():
    # allowed_routes needs to match the blueprint.route names
    allowed_routes = ['auth.login', 'auth.auth_login', 'static', 'public.public_menu', 'public.generate_qr']
    if request.endpoint and request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('auth.login'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("Access Denied: Admin privileges required.", "error")
            return redirect(url_for('public.home'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route("/login")
def login():
    if 'user_id' in session:
        return redirect(url_for('public.home'))
    return render_template("login.html")

@auth_bp.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json()
    token = data.get('token')
    if not token:
        return jsonify({"error": "No token provided"}), 400
        
    try:
        decoded_token = firebase_auth.verify_id_token(token, clock_skew_seconds=60)
        session['user_id'] = decoded_token['uid']
        email = decoded_token.get('email')
        session['email'] = email
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT r.role_name FROM users u JOIN roles r ON u.role_id = r.role_id WHERE u.username = %s", (email,))
        user_db = cursor.fetchone()
        cursor.close()
        db.close()
        
        if not user_db:
            return jsonify({"error": "Unauthorized email address. Please contact your administrator."}), 403
            
        if user_db['role_name'] == 'admin':
            session['role'] = 'admin'
        elif user_db['role_name'] == 'kitchen':
            session['role'] = 'kitchen'
        else:
            session['role'] = 'staff'
            
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route("/manage-users", methods=["GET", "POST"])
@admin_required
def manage_users():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            email = request.form.get("email", "").strip().lower()
            role_id = request.form.get("role_id")
            if email and role_id:
                try:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, role_id) VALUES (%s, %s, %s)",
                        (email, "firebase_auth", role_id)
                    )
                    db.commit()
                    flash(f"User {email} added successfully.", "success")
                except mysql.connector.errors.IntegrityError:
                    flash(f"User {email} already exists.", "error")
        elif action == "delete":
            user_id = request.form.get("user_id")
            if user_id:
                cursor.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
                u = cursor.fetchone()
                if u and u['username'] == session.get('email'):
                    flash("You cannot delete your own account while logged in.", "error")
                else:
                    cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                    db.commit()
                    flash("User removed successfully.", "success")
                    
        return redirect(url_for('auth.manage_users'))

    cursor.execute("""
        SELECT u.user_id, u.username, r.role_name 
        FROM users u 
        JOIN roles r ON u.role_id = r.role_id 
        ORDER BY r.role_id, u.username
    """)
    users = cursor.fetchall()
    
    cursor.execute("SELECT * FROM roles")
    roles = cursor.fetchall()
    
    cursor.close()
    db.close()
    
    return render_template("manage_users.html", users=users, roles=roles)
