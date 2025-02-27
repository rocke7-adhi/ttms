from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Database connection
db = mysql.connector.connect(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    port=app.config['MYSQL_PORT'],
    database=app.config['MYSQL_DB'],
    charset='utf8'
)

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    if user:
        return User(user['id'], user['username'], user['role'])
    return None

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        selected_role = request.form['role']
        
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s AND role = %s', 
                      (username, password, selected_role))
        user = cursor.fetchone()
        cursor.close()
        
        if user:
            user_obj = User(user['id'], user['username'], user['role'])
            login_user(user_obj)
            return redirect(url_for(f'{user["role"]}_dashboard'))
        flash('Invalid credentials or incorrect role selected')
    return render_template('login.html')

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    # Get counts for dashboard
    cursor = db.cursor(dictionary=True)
    
    # Get staff count
    cursor.execute('SELECT COUNT(*) as count FROM staff')
    staff_count = cursor.fetchone()['count']
    
    # Get class count
    cursor.execute('SELECT COUNT(*) as count FROM classes')
    class_count = cursor.fetchone()['count']
    
    # Get pending leave requests
    cursor.execute('SELECT COUNT(*) as count FROM leave_requests WHERE status = "pending"')
    pending_leaves = cursor.fetchone()['count']
    
    cursor.close()
    
    return render_template('admin/dashboard.html',
                         staff_count=staff_count,
                         class_count=class_count,
                         pending_leaves=pending_leaves)

@app.route('/admin/manage-staff', methods=['GET', 'POST'])
@login_required
def manage_staff():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Handle staff creation
        name = request.form['name']
        department = request.form['department']
        username = request.form['username']
        password = request.form['password']
        
        cursor = db.cursor()
        try:
            # First create user
            cursor.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, "staff")',
                          (username, password, 'staff'))
            user_id = cursor.lastrowid
            
            # Then create staff
            cursor.execute('INSERT INTO staff (user_id, name, department) VALUES (%s, %s, %s)',
                          (user_id, name, department))
            
            db.commit()
            flash('Staff added successfully')
        except mysql.connector.Error as err:
            db.rollback()
            flash(f'Error adding staff: {err}')
        cursor.close()
    
    # Get staff list for display
    cursor = db.cursor(dictionary=True)
    cursor.execute('''
        SELECT s.*, u.username, GROUP_CONCAT(c.name) as classes
        FROM staff s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN assignments a ON s.id = a.staff_id
        LEFT JOIN classes c ON a.class_id = c.id
        GROUP BY s.id
    ''')
    staff_list = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/manage_staff.html', staff_list=staff_list)

@app.route('/admin/edit-staff/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def edit_staff(staff_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        username = request.form['username']
        password = request.form.get('password')  # Optional password change
        
        try:
            # Update staff details
            cursor.execute('UPDATE staff SET name = %s, department = %s WHERE id = %s',
                         (name, department, staff_id))
            
            # Get user_id for this staff
            cursor.execute('SELECT user_id FROM staff WHERE id = %s', (staff_id,))
            user_id = cursor.fetchone()['user_id']
            
            # Update user details
            if password:
                cursor.execute('UPDATE users SET username = %s, password = %s WHERE id = %s',
                             (username, password, user_id))
            else:
                cursor.execute('UPDATE users SET username = %s WHERE id = %s',
                             (username, user_id))
            
            db.commit()
            flash('Staff updated successfully')
            return redirect(url_for('manage_staff'))
        except mysql.connector.Error as err:
            db.rollback()
            flash(f'Error updating staff: {err}')
    
    # Get staff details for editing
    cursor.execute('''
        SELECT s.*, u.username 
        FROM staff s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = %s
    ''', (staff_id,))
    staff = cursor.fetchone()
    cursor.close()
    
    if not staff:
        flash('Staff not found')
        return redirect(url_for('manage_staff'))
    
    return render_template('admin/edit_staff.html', staff=staff)

@app.route('/admin/delete-staff/<int:staff_id>')
@login_required
def delete_staff(staff_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    try:
        # Get user_id first
        cursor.execute('SELECT user_id FROM staff WHERE id = %s', (staff_id,))
        result = cursor.fetchone()
        if result:
            user_id = result['user_id']
            # Delete staff (this will cascade to assignments)
            cursor.execute('DELETE FROM staff WHERE id = %s', (staff_id,))
            # Delete user
            cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
            db.commit()
            flash('Staff deleted successfully')
        else:
            flash('Staff not found')
    except mysql.connector.Error as err:
        db.rollback()
        flash(f'Error deleting staff: {err}')
    
    cursor.close()
    return redirect(url_for('manage_staff'))

# Staff routes
@app.route('/staff/dashboard')
@login_required
def staff_dashboard():
    if current_user.role != 'staff':
        return redirect(url_for('login'))
    return render_template('staff/dashboard.html')

@app.route('/staff/leave-request', methods=['GET', 'POST'])
@login_required
def leave_request():
    if current_user.role != 'staff':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        
        cursor = db.cursor()
        cursor.execute('INSERT INTO leave_requests (staff_id, start_date, end_date, reason) VALUES (%s, %s, %s, %s)',
                      (current_user.id, start_date, end_date, reason))
        db.commit()
        cursor.close()
        flash('Leave request submitted successfully')
    
    return render_template('staff/leave_request.html')

# Student routes
@app.route('/student/timetable')
@login_required
def student_timetable():
    if current_user.role != 'student':
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    cursor.execute('''
        SELECT t.*, s.name as staff_name, c.name as class_name 
        FROM timetable t 
        JOIN staff s ON t.staff_id = s.id 
        JOIN classes c ON t.class_id = c.id 
        WHERE t.class_id = (SELECT class_id FROM student_classes WHERE student_id = %s)
    ''', (current_user.id,))
    timetable = cursor.fetchall()
    cursor.close()
    
    return render_template('student/timetable.html', timetable=timetable)

@app.route('/test_db')
def test_db():
    try:
        cursor = db.cursor()
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        cursor.close()
        return 'Database connection successful!'
    except Exception as e:
        return f'Database connection failed: {str(e)}'

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/manage/classes', methods=['GET', 'POST'])
@login_required
def manage_classes():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Handle class creation
        name = request.form['name']
        subject = request.form['subject']
        department = request.form['department']
        semester = request.form['semester']
        section = request.form['section']
        teacher_id = request.form['teacher_id']
        schedule = request.form['schedule']
        
        try:
            cursor.execute('''
                INSERT INTO classes 
                (name, subject, department, semester, section, teacher_id, schedule) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (name, subject, department, semester, section, teacher_id, schedule))
            db.commit()
            flash('Class added successfully')
        except mysql.connector.Error as err:
            db.rollback()
            flash(f'Error adding class: {err}')
    
    # Get all classes with teacher names
    cursor.execute('''
        SELECT c.*, s.name as teacher_name, s.department as teacher_department
        FROM classes c 
        LEFT JOIN staff s ON c.teacher_id = s.id
    ''')
    classes = cursor.fetchall()
    
    # Get all teachers for the dropdown
    cursor.execute('SELECT id, name, department FROM staff')
    teachers = cursor.fetchall()
    
    cursor.close()
    
    return render_template('manage_classes.html', classes=classes, teachers=teachers)

@app.route('/admin/leave-requests')
@login_required
def admin_leave_requests():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    cursor = db.cursor(dictionary=True)
    cursor.execute('''
        SELECT lr.*, s.name as staff_name, s.department 
        FROM leave_requests lr
        JOIN staff s ON lr.staff_id = s.id
        ORDER BY lr.created_at DESC
    ''')
    leave_requests = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/leave_requests.html', leave_requests=leave_requests)

@app.route('/admin/leave-requests/<int:request_id>/<string:action>')
@login_required
def handle_leave_request(request_id, action):
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    if action not in ['approve', 'reject']:
        flash('Invalid action')
        return redirect(url_for('admin_leave_requests'))
    
    status = 'approved' if action == 'approve' else 'rejected'
    
    cursor = db.cursor()
    try:
        cursor.execute('UPDATE leave_requests SET status = %s WHERE id = %s',
                      (status, request_id))
        db.commit()
        flash(f'Leave request {status} successfully')
    except mysql.connector.Error as err:
        db.rollback()
        flash(f'Error updating leave request: {err}')
    cursor.close()
    
    return redirect(url_for('admin_leave_requests'))

@app.route('/admin/leave-requests/delete/<int:request_id>')
@login_required
def delete_leave_request(request_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    cursor = db.cursor()
    try:
        cursor.execute('DELETE FROM leave_requests WHERE id = %s', (request_id,))
        db.commit()
        flash('Leave request deleted successfully')
    except mysql.connector.Error as err:
        db.rollback()
        flash(f'Error deleting leave request: {err}')
    cursor.close()
    
    return redirect(url_for('admin_leave_requests'))

if __name__ == '__main__':
    app.run(debug=True) 