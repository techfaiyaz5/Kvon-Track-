import os
import base64
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import or_, func
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# --- APP INITIALIZATION ---
app = Flask(__name__)

app.config['SECRET_KEY'] = 'kvon_tech_enterprise_ultra_2026'
app.config['ADMIN_KEY'] = "KVON_BOSS_2026"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'kvon_final_production.db')
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    emp_id = db.Column(db.String(50), unique=True)
    dob = db.Column(db.String(20))
    role = db.Column(db.String(20), default='employee')
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    emp_full_name = db.Column(db.String(160))
    check_in = db.Column(db.DateTime, default=datetime.now)
    check_out = db.Column(db.DateTime, nullable=True)
    location_in = db.Column(db.String(255))
    location_out = db.Column(db.String(255))
    selfie = db.Column(db.String(255))
    total_seconds = db.Column(db.Integer, default=0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- HELPER FUNCTIONS ---

def calculate_hours(logs):
    total_sec = 0
    if not logs:
        return "00:00 Hr"
    for log in logs:
        if log.check_in and log.check_out:
            diff = (log.check_out - log.check_in).total_seconds()
            total_sec += diff
    hrs = int(total_sec // 3600)
    mins = int((total_sec % 3600) // 60)
    return f"{hrs:02d}:{mins:02d} Hr"

# --- CORE ROUTES ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        uname = request.form.get('username').lower()
        email = request.form.get('email').lower()
        key = request.form.get('admin_key')

        if User.query.filter((User.username == uname) | (User.email == email)).first():
            flash('Username or Email already exists!', 'danger')
            return redirect(url_for('signup'))

        is_admin = (key == app.config['ADMIN_KEY'])
        new_user = User(
            username=uname, email=email,
            password=request.form.get('password'),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            emp_id=request.form.get('emp_id'),
            dob=request.form.get('dob'),
            role='admin' if is_admin else 'employee',
            status='approved' if is_admin else 'pending'
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration Successful! Wait for Admin approval.' if not is_admin else 'Admin Ready!', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('identity').lower()
        password = request.form.get('password')
        role_type = request.form.get('login_as')

        user = User.query.filter((User.username == identity) | (User.email == identity)).first()

        if user and user.password == password and user.role == role_type:
            if user.status != 'approved':
                flash('Your account is pending admin approval!', 'warning')
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Invalid Login Credentials!', 'danger')
    return render_template('login.html')

# --- DASHBOARD ---

@app.route('/dashboard')
@login_required
def dashboard():
    today_date = datetime.now().date()
    yesterday_date = today_date - timedelta(days=1)
    week_start = today_date - timedelta(days=7)
    date_display = datetime.now().strftime("%A, %d %B %Y")

    if current_user.role == 'admin':
        logs = Attendance.query.order_by(Attendance.id.desc()).all()
        pending_users = User.query.filter_by(status='pending').all()
        return render_template('admin_dashboard.html', logs=logs, pending=pending_users, today=date_display)

    t_logs = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        func.date(Attendance.check_in) == today_date
    ).all()
    y_logs = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        func.date(Attendance.check_in) == yesterday_date
    ).all()
    w_logs = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        func.date(Attendance.check_in) >= week_start
    ).all()

    stats = {
        'today': calculate_hours(t_logs),
        'yesterday': calculate_hours(y_logs),
        'weekly': calculate_hours(w_logs)
    }

    recent_activity = Attendance.query.filter_by(
        user_id=current_user.id
    ).order_by(Attendance.id.desc()).limit(10).all()

    active_session = Attendance.query.filter_by(
        user_id=current_user.id, check_out=None
    ).first()

    return render_template('emp_dashboard.html',
        logs=recent_activity,
        active=active_session,
        stats=stats,
        today_date=date_display
    )

# --- ATTENDANCE PUNCH ---

@app.route('/punch', methods=['POST'])
@login_required
def punch():
    try:
        data = request.get_json()
        if not data or 'selfie' not in data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        active = Attendance.query.filter_by(user_id=current_user.id, check_out=None).first()

        img_str = data['selfie'].split(",")[1]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        img_name = f"punch_{current_user.id}_{timestamp}.png"
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], img_name)

        with open(img_path, "wb") as f:
            f.write(base64.b64decode(img_str))

        if not active:
            new_log = Attendance(
                user_id=current_user.id,
                emp_full_name=f"{current_user.first_name} {current_user.last_name}",
                location_in=data.get('location', 'Unknown Location'),
                selfie=img_name
            )
            db.session.add(new_log)
            res_msg = "Check-In Success"
        else:
            active.check_out = datetime.now()
            active.location_out = data.get('location', 'Unknown Location')
            res_msg = "Check-Out Success"

        db.session.commit()
        return jsonify({"status": "success", "message": res_msg})

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ADMIN ACTIONS ---

@app.route('/admin/approve/<int:user_id>')
@login_required
def approve_user(user_id):
    if current_user.role != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))
    target_user = User.query.get_or_404(user_id)
    target_user.status = 'approved'
    db.session.commit()
    flash(f'Account for {target_user.first_name} has been approved!', 'success')
    return redirect(url_for('dashboard'))

# --- PROFILE ---

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    current_user.first_name = request.form.get('first_name')
    current_user.last_name = request.form.get('last_name')
    db.session.commit()
    flash("Profile updated successfully!", "success")
    return redirect(url_for('dashboard'))

# --- REPORTS ---

@app.route('/my-attendance')
@app.route('/daily-login-hrs')
@login_required
def reports():
    logs = Attendance.query.filter_by(
        user_id=current_user.id
    ).order_by(Attendance.id.desc()).all()
    return render_template('attendance_view.html', logs=logs)

# --- DOWNLOAD EXCEL ---
@app.route('/download/excel')
@login_required
def download_excel():
    logs = Attendance.query.filter_by(user_id=current_user.id).all()
    if not logs:
        flash("No data found!", "warning")
        return redirect(url_for('dashboard'))

    data_list = []
    for l in logs:
        data_list.append({
            "Date": l.check_in.strftime('%Y-%m-%d'),
            "Check-In": l.check_in.strftime('%I:%M %p'),
            "Check-Out": l.check_out.strftime('%I:%M %p') if l.check_out else "N/A",
            "Location In": l.location_in or "N/A",
            "Location Out": l.location_out or "N/A",
        })

    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name=f"Attendance_{current_user.emp_id}.xlsx")

# --- DOWNLOAD PDF ---
@app.route('/download/pdf')
@login_required
def download_pdf():
    logs = Attendance.query.filter_by(user_id=current_user.id).all()
    if not logs:
        flash("No data found!", "warning")
        return redirect(url_for('dashboard'))

    output = BytesIO()
    p = canvas.Canvas(output, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, f"Attendance Report — {current_user.first_name} {current_user.last_name}")
    p.setFont("Helvetica", 10)
    p.drawString(100, 730, f"Employee ID: {current_user.emp_id}  |  Generated: {datetime.now().strftime('%d %b %Y')}")
    p.line(100, 720, 510, 720)

    y = 700
    p.setFont("Helvetica-Bold", 10)
    p.drawString(100, y, "Date")
    p.drawString(200, y, "Check-In")
    p.drawString(290, y, "Check-Out")
    p.drawString(380, y, "Status")
    y -= 20

    p.setFont("Helvetica", 10)
    for l in logs:
        if y < 60:
            p.showPage()
            y = 750
        status = "Completed" if l.check_out else "Ongoing"
        p.drawString(100, y, l.check_in.strftime('%d %b %Y'))
        p.drawString(200, y, l.check_in.strftime('%I:%M %p'))
        p.drawString(290, y, l.check_out.strftime('%I:%M %p') if l.check_out else "--:--")
        p.drawString(380, y, status)
        y -= 18

    p.save()
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name=f"Attendance_{current_user.emp_id}.pdf")

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- APP RUNNER ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)