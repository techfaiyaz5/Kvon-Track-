from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os, base64
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from sqlalchemy import or_, func

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = 'kvon_tech_ultra_secure_2026'
app.config['ADMIN_KEY'] = "KVON_BOSS_2026" 

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'kvon_final_production.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    emp_full_name = db.Column(db.String(160))
    check_in = db.Column(db.DateTime, default=datetime.now)
    check_out = db.Column(db.DateTime)
    location = db.Column(db.String(200))
    selfie = db.Column(db.String(200))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- HELPER: HOURS CALCULATOR ---
def get_total_hrs(logs):
    total_seconds = 0
    if not logs:
        return "00:00 Hr"
    for log in logs:
        if log.check_out:
            diff = log.check_out - log.check_in
            total_seconds += diff.total_seconds()
    hrs = int(total_seconds // 3600)
    mins = int((total_seconds % 3600) // 60)
    return f"{hrs:02d}:{mins:02d} Hr"

# --- AUTH ROUTES ---
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        uname = request.form.get('username').lower()
        key = request.form.get('admin_key')
        
        is_admin = (key == app.config['ADMIN_KEY'])
        role = 'admin' if is_admin else 'employee'
        status = 'approved' if is_admin else 'pending'

        if User.query.filter_by(username=uname).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('signup'))

        new_user = User(
            username=uname, email=request.form.get('email'),
            password=request.form.get('password'),
            first_name=request.form.get('first_name'), last_name=request.form.get('last_name'),
            emp_id=request.form.get('emp_id'), dob=request.form.get('dob'),
            role=role, status=status
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Admin Account Ready!' if is_admin else 'Registered! Wait for Admin Approval.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('identity').lower()
        password = request.form.get('password')
        login_as = request.form.get('login_as') 
        
        user = User.query.filter((User.username == identity) | (User.email == identity)).first()
        if user and user.password == password and user.role == login_as:
            if user.status != 'approved':
                flash('Your account is pending admin approval!', 'warning')
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid Credentials or Role!', 'danger')
    return render_template('login.html')

# --- DASHBOARD & STATS ---
@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().date()
    today_str = datetime.now().strftime("%A, %d %B %Y")

    if current_user.role == 'admin':
        all_logs = Attendance.query.order_by(Attendance.id.desc()).all()
        pending = User.query.filter_by(status='pending').all()
        return render_template('admin_dashboard.html', logs=all_logs, pending=pending, today=today_str)
    
    # Calculate 3-Column Stats
    t_logs = Attendance.query.filter(Attendance.user_id==current_user.id, func.date(Attendance.check_in) == today).all()
    y_logs = Attendance.query.filter(Attendance.user_id==current_user.id, func.date(Attendance.check_in) == (today - timedelta(days=1))).all()
    w_logs = Attendance.query.filter(Attendance.user_id==current_user.id, func.date(Attendance.check_in) >= (today - timedelta(days=7))).all()

    stats = {
        'today': get_total_hrs(t_logs),
        'yesterday': get_total_hrs(y_logs),
        'weekly': get_total_hrs(w_logs)
    }

    recent_logs = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.id.desc()).limit(5).all()
    active = Attendance.query.filter_by(user_id=current_user.id, check_out=None).first()
    
    return render_template('emp_dashboard.html', logs=recent_logs, active=active, stats=stats, today_date=today_str)

# --- ATTENDANCE ACTIONS ---
@app.route('/punch', methods=['POST'])
@login_required
def punch():
    data = request.get_json()
    active = Attendance.query.filter_by(user_id=current_user.id, check_out=None).first()
    
    img_data = data['selfie'].split(",")[1]
    filename = f"selfie_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(img_data))
    
    if not active:
        db.session.add(Attendance(
            user_id=current_user.id, 
            emp_full_name=f"{current_user.first_name} {current_user.last_name}",
            location=data['location'], 
            selfie=filename
        ))
    else:
        active.check_out = datetime.now()
    
    db.session.commit()
    return jsonify({"status": "success"})

# --- REPORT VIEWS & EXPORTS ---
@app.route('/my-attendance')
@app.route('/daily-login-hrs')
@login_required
def reports():
    logs = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.id.desc()).all()
    return render_template('attendance_view.html', logs=logs)

@app.route('/download/<fmt>')
@login_required
def download(fmt):
    logs = Attendance.query.filter_by(user_id=current_user.id).all()
    if not logs:
        flash("No logs found to export!", "warning")
        return redirect(url_for('reports'))

    data = [{"Date": l.check_in.strftime('%Y-%m-%d'), "In": l.check_in.strftime('%I:%M %p'), "Out": l.check_out.strftime('%I:%M %p') if l.check_out else "N/A"} for l in logs]
    df = pd.DataFrame(data)
    output = BytesIO()
    
    if fmt == 'excel':
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f"Attendance_Report_{current_user.first_name}.xlsx")
    
    elif fmt == 'pdf':
        p = canvas.Canvas(output, pagesize=letter)
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 750, f"Attendance Report: {current_user.first_name} {current_user.last_name}")
        p.setFont("Helvetica", 12)
        y = 700
        for i in data:
            if y < 50: # New page logic
                p.showPage()
                y = 750
            p.drawString(100, y, f"{i['Date']} | In: {i['In']} | Out: {i['Out']}")
            y -= 25
        p.save()
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f"Attendance_Report_{current_user.first_name}.pdf")

# --- ADMIN ACTIONS ---
@app.route('/admin/approve/<int:user_id>')
@login_required
def approve_user(user_id):
    if current_user.role == 'admin':
        u = User.query.get(user_id)
        if u:
            u.status = 'approved'
            db.session.commit()
            flash(f"User {u.first_name} approved!", "success")
    return redirect(url_for('dashboard'))

# --- PROFILE & LOGOUT ---
@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    current_user.first_name = request.form.get('first_name')
    current_user.last_name = request.form.get('last_name')
    db.session.commit()
    flash("Profile updated successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)