import sys
import subprocess
import importlib.util

def check_and_install_dependencies():
    """
    Automatically checks for required Python packages and installs missing ones.
    This ensures all dependencies are available before the application starts.
    """
    required_packages = {
        'flask': 'Flask',
        'pandas': 'pandas',
        'openpyxl': 'openpyxl',
        'pymysql': 'PyMySQL',
        'werkzeug': 'Werkzeug',
    }
    
    missing_packages = []
    
    print("Checking dependencies...")
    for package, display_name in required_packages.items():
        if importlib.util.find_spec(package) is None:
            print(f"✗ {display_name} is missing")
            missing_packages.append(package)
        else:
            print(f"✓ {display_name} is installed")
    
    if missing_packages:
        print("\nInstalling missing packages...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("All required packages have been installed successfully!")
            
            print("Restarting application...")
            python = sys.executable
            script = sys.argv[0]
            subprocess.call([python, script] + sys.argv[1:])
            sys.exit(0)
        except Exception as e:
            print(f"\nFailed to install packages automatically: {e}")
            print("\nPlease manually install the required packages with:")
            print(f"pip install {' '.join(missing_packages)}")
            input("\nPress Enter to exit...")
            sys.exit(1)

check_and_install_dependencies()

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import time
import mysql.connector
import os
from functools import wraps
import subprocess
import pandas as pd
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = os.urandom(24)

def get_db_connection():
    """
    Establishes connection to MySQL database.
    Returns connection object or None if connection fails.
    """
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1234",
            database="vms"
        )
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def check_db_connection():
    """
    Checks if database connection is active and returns status string.
    Used for displaying connection status in the UI.
    """
    try:
        connection = get_db_connection()
        if connection and connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            db_version = cursor.fetchone()
            cursor.close()
            connection.close()
            return "Connected"
        else:
            return "Disconnected"
    except Exception as e:
        return f"Disconnected: {str(e)}"

def admin_required(f):
    """
    Decorator to protect admin-only routes.
    Redirects to admin login if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    """
    Decorator to protect staff-only routes.
    Redirects to staff login if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'staff_logged_in' not in session:
            return redirect(url_for('staff_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Root route that redirects to home page."""
    return redirect(url_for('home'))

@app.route('/admin')
def admin_redirect():
    """Public admin route that redirects to admin login."""
    return redirect(url_for('admin_login'))

@app.route('/home')
def home():
    """Main homepage route with theme support."""
    theme = session.get('theme', 'light')
    return render_template('home.html', theme=theme)

@app.route('/loading')
def loading():
    """Loading page route for displaying processing animations."""
    return render_template('loading.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard route that shows database connection status."""
    db_status = check_db_connection()
    return render_template('dashboard.html', status=db_status)

@app.route('/refresh_status')
def refresh_status():
    """API endpoint to refresh database connection status."""
    db_status = check_db_connection()
    return render_template('status_indicator.html', status=db_status)

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """
    Admin login route with authentication.
    Handles both GET (display form) and POST (process login) requests.
    """
    if 'admin_logged_in' in session:
        return redirect(url_for('admin'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == "admin" and password == "admin123":
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin_login.html', error="Invalid credentials")
    
    return render_template('admin_login.html', theme=session.get('theme', 'light'))

@app.route('/admin/dashboard')
@admin_required
def admin():
    """
    Main admin dashboard displaying system statistics and recent logs.
    Protected by admin_required decorator.
    """
    theme = session.get('theme', 'light')
    active_submenu = session.get('active_submenu')
    db_status = check_db_connection()
    stats = {
        'total_users': 0,
        'active_sessions': 0,
        'total_visitors': 0
    }
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as staff_count FROM staffs")
        staff_count = cursor.fetchone()['staff_count']
        
        cursor.execute("SELECT COUNT(*) as visitor_count FROM visitors")
        visitor_count = cursor.fetchone()['visitor_count']
        
        cursor.execute("""
            SELECT COUNT(*) as active_count 
            FROM logbook 
            WHERE check_out IS NULL
        """)
        active_count = cursor.fetchone()['active_count']
        
        cursor.execute("""
            SELECT 
                l.log_id,
                l.check_in,
                l.check_out,
                v.name as visitor_name
            FROM logbook l
            LEFT JOIN visitors v ON l.visitor_id = v.visitor_id
            ORDER BY l.check_in DESC
            LIMIT 5
        """)
        logs = cursor.fetchall()
        
        stats.update({
            'total_users': staff_count + visitor_count,
            'active_sessions': active_count,
            'total_visitors': visitor_count
        })
        
    except Exception as e:
        print(f"Database Error: {e}")
        db_status = "Disconnected"
        logs = []
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
    
    return render_template('admin.html',
                         status=db_status,
                         theme=theme,
                         active_submenu=active_submenu,
                         active_page='dashboard',
                         stats=stats,
                         logs=logs)

@app.route('/admin/add-staff', methods=['GET', 'POST'])
@admin_required
def add_staff():
    """Route for adding new staff members (legacy route)."""
    if request.method == 'POST':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            name = request.form['name']
            email = request.form['email']
            department = request.form['department']
            
            sql = "INSERT INTO staffs (name, email, department) VALUES (%s, %s, %s)"
            values = (name, email, department)
            cursor.execute(sql, values)
            connection.commit()
            
            return redirect(url_for('admin'))
            
        except Exception as e:
            print(f"Error: {e}")
            return "Error adding staff"
        finally:
            if connection:
                cursor.close()
                connection.close()
                
    return render_template('add_staff.html')

@app.route('/admin/add-visitor', methods=['GET', 'POST'])
@admin_required
def add_visitor():
    """Route for adding new visitors (legacy route)."""
    if request.method == 'POST':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            name = request.form['name']
            purpose = request.form['purpose']
            host = request.form['host']
            
            sql = "INSERT INTO visitors (name, purpose, host) VALUES (%s, %s, %s)"
            values = (name, purpose, host)
            cursor.execute(sql, values)
            connection.commit()
            
            return redirect(url_for('admin'))
            
        except Exception as e:
            print(f"Error: {e}")
            return "Error adding visitor"
        finally:
            if connection:
                cursor.close()
                connection.close()
                
    return render_template('add_visitor.html')

@app.route('/admin/users/staff', methods=['GET', 'POST'])
@admin_required
def manage_staff():
    """
    Staff management route that handles listing, searching, and adding staff members.
    Supports search functionality and form submission for new staff.
    """
    theme = session.get('theme', 'light')
    status = check_db_connection()
    search = request.args.get('search', '')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            address = request.form['address']
            password = request.form['password']
            
            cursor.execute("""
                INSERT INTO staffs (name, email, address, password) 
                VALUES (%s, %s, %s, %s)
            """, (name, email, address, password))
            conn.commit()
            
            return redirect(url_for('manage_staff'))
        
        query = "SELECT * FROM staffs WHERE 1=1"
        params = []
        
        if search:
            query += " AND (name LIKE %s OR email LIKE %s OR address LIKE %s)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        staff_list = cursor.fetchall()
        
        return render_template('staff.html', 
                            staff=staff_list,
                            theme=theme,
                            status=status,
                            active_page='staffs',
                            active_submenu='users')
        
    except Exception as e:
        print(f"Error: {e}")
        return render_template('staff.html',
                            staff=[],
                            theme=theme,
                            status="Disconnected",
                            active_page='staffs',
                            active_submenu='users')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin/users/staff/<int:staff_id>/edit', methods=['POST'])
@app.route('/admin/users/staff//<int:staff_id>/edit', methods=['POST'])
@admin_required
def edit_staff(staff_id):
    """
    Edit staff member information.
    Handles double slash URLs for compatibility.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        password = request.form.get('password')
        
        if password:
            cursor.execute("""
                UPDATE staffs 
                SET name = %s, email = %s, address = %s, password = %s
                WHERE staff_id = %s
            """, (name, email, address, password, staff_id))
        else:
            cursor.execute("""
                UPDATE staffs 
                SET name = %s, email = %s, address = %s
                WHERE staff_id = %s
            """, (name, email, address, staff_id))
            
        conn.commit()
        
        return redirect(url_for('manage_staff'))
    except Exception as e:
        print(f"Error updating staff: {e}")
        return "Database error", 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin/users/staff/<int:staff_id>/delete', methods=['POST'])
@admin_required
def delete_staff(staff_id):
    """Delete a staff member from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM staffs WHERE staff_id = %s", (staff_id,))
        conn.commit()
        
        return redirect(url_for('manage_staff'))
    except Exception as e:
        print(f"Error deleting staff: {e}")
        return "Database error", 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin/users/visitors', methods=['GET', 'POST'])
@admin_required
def manage_visitors():
    """
    Visitor management route that handles listing, searching, and adding visitors.
    Supports search functionality across multiple visitor fields.
    """
    theme = session.get('theme', 'light')
    status = check_db_connection()
    search = request.args.get('search', '')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            name = request.form['name']
            age = request.form['age']
            sex = request.form['sex']
            email = request.form['email']
            address = request.form['address']
            id_proof_type = request.form['id_proof_type']
            proof_number = request.form['proof_number']
            
            cursor.execute("""
                INSERT INTO visitors (name, age, sex, email, address, id_proof_type, proof_number) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, int(age), sex, email, address, id_proof_type, proof_number))
            conn.commit()
            
            return redirect(url_for('manage_visitors'))
        
        query = "SELECT * FROM visitors WHERE 1=1"
        params = []
        
        if search:
            query += " AND (name LIKE %s OR email LIKE %s OR address LIKE %s OR proof_number LIKE %s OR id_proof_type LIKE %s)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term, search_term, search_term])
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        visitors_list = cursor.fetchall()
        
        return render_template('visitors.html', 
                            visitors=visitors_list,
                            theme=theme,
                            status=status,
                            active_page='visitors',
                            active_submenu='users')
        
    except Exception as e:
        print(f"Error: {e}")
        return render_template('visitors.html',
                            visitors=[],
                            theme=theme,
                            status="Disconnected",
                            active_page='visitors',
                            active_submenu='users')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin/users/visitors/<int:visitor_id>/edit', methods=['POST'])
@admin_required
def edit_visitor(visitor_id):
    """Edit visitor information in the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        name = request.form['name']
        age = request.form['age']
        sex = request.form['sex']
        email = request.form['email']
        address = request.form['address']
        id_proof_type = request.form['id_proof_type']
        proof_number = request.form['proof_number']
        
        cursor.execute("""
            UPDATE visitors 
            SET name = %s, age = %s, sex = %s, email = %s, address = %s, 
                id_proof_type = %s, proof_number = %s
            WHERE visitor_id = %s
        """, (name, int(age), sex, email, address, id_proof_type, proof_number, visitor_id))
        conn.commit()
        
        return redirect(url_for('manage_visitors'))
    except Exception as e:
        print(f"Error updating visitor: {e}")
        return "Database error", 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin/users/visitors/<int:visitor_id>/delete', methods=['POST'])
@admin_required
def delete_visitor(visitor_id):
    """
    Delete a visitor from the database.
    Also removes any associated logbook entries.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as log_count FROM logbook WHERE visitor_id = %s", (visitor_id,))
        result = cursor.fetchone()
        log_count = result[0] if result else 0
        
        if log_count > 0:
            cursor.execute("DELETE FROM logbook WHERE visitor_id = %s", (visitor_id,))
        
        cursor.execute("DELETE FROM visitors WHERE visitor_id = %s", (visitor_id,))
        conn.commit()
        
        return redirect(url_for('manage_visitors'))
    except Exception as e:
        print(f"Error deleting visitor: {e}")
        return "Database error", 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin/logs')
@admin_required
def view_logs():
    """
    Display visitor logs with search and filtering capabilities.
    Supports filtering by date range, time range, and visitor name search.
    """
    theme = session.get('theme', 'light')
    status = check_db_connection()
    active_submenu = session.get('active_submenu')
    
    search = request.args.get('search', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    time_from = request.args.get('time_from', '')
    time_to = request.args.get('time_to', '')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                l.log_id,
                l.check_in,
                l.check_out,
                v.name as visitor_name
            FROM logbook l
            LEFT JOIN visitors v ON l.visitor_id = v.visitor_id
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND v.name LIKE %s"
            params.append(f"%{search}%")
        
        if date_from:
            query += " AND DATE(l.check_in) >= %s"
            params.append(date_from)
        
        if date_to:
            query += " AND DATE(l.check_in) <= %s"
            params.append(date_to)
        
        if time_from:
            query += " AND TIME(l.check_in) >= %s"
            params.append(time_from)
        
        if time_to:
            query += " AND TIME(l.check_in) <= %s"
            params.append(time_to)
        
        query += " ORDER BY l.check_in DESC"
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        
        show_filter_panel = bool(date_from or date_to or time_from or time_to)
        
        return render_template('logs.html',
                             logs=logs,
                             theme=theme,
                             status=status,
                             active_page='logbook',
                             active_submenu=active_submenu,
                             show_filter_panel=show_filter_panel)
                             
    except Exception as e:
        print(f"Error: {e}")
        return render_template('logs.html',
                             logs=[],
                             theme=theme,
                             status='Disconnected',
                             active_page='logbook',
                             active_submenu=active_submenu)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin/settings')
@admin_required
def settings():
    """Admin settings page for system configuration."""
    status = check_db_connection()
    active_submenu = session.get('active_submenu')
    return render_template('settings.html', 
                          active_page='settings',
                          status=status,
                          active_submenu=active_submenu,
                          theme=session.get('theme', 'light'))

@app.route('/toggle-theme', methods=['POST'])
def toggle_theme():
    """Toggle between light and dark themes."""
    current_theme = session.get('theme', 'light')
    session['theme'] = 'dark' if current_theme == 'light' else 'light'
    return redirect(request.referrer)

@app.route('/toggle-submenu', methods=['POST'])
def toggle_submenu():
    """Toggle sidebar submenu visibility state."""
    current_submenu = request.form.get('submenu')
    active_submenu = session.get('active_submenu')
    
    if request.referrer and ('users' in request.referrer or 
                            'staff' in request.referrer or 
                            'visitors' in request.referrer):
        session['active_submenu'] = current_submenu
    else:
        if active_submenu == current_submenu:
            session.pop('active_submenu', None)
        else:
            session['active_submenu'] = current_submenu
    
    return redirect(request.referrer)

@app.template_filter('now')
def filter_now(format_string, format_params='%Y-%m-%d %H:%M:%S'):
    """Custom template filter for displaying current time."""
    return time.strftime(format_params)

@app.route('/admin/api/backup-database', methods=['POST'])
@admin_required
def backup_database():
    """
    Creates a database backup using mysqldump and returns it as a download.
    Generates timestamped backup files in SQL format.
    """
    try:
        backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"vms_backup_{timestamp}.sql")
        
        db_config = {
            "host": "localhost",
            "user": "root",
            "password": "1234",
            "database": "vms"
        }
        
        cmd = [
            'mysqldump',
            f'--host={db_config["host"]}',
            f'--user={db_config["user"]}',
            f'--password={db_config["password"]}',
            db_config["database"]
        ]
        
        with open(backup_file, 'wb') as f:
            process = subprocess.Popen(cmd, stdout=f)
            process.wait()
            
        return send_file(backup_file, as_attachment=True, download_name=f"vms_backup_{timestamp}.sql")
        
    except Exception as e:
        print(f"Backup error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/export-all-logs', methods=['POST'])
@admin_required
def export_all_logs():
    """
    Exports all visitor logs to an Excel file.
    Includes complete visitor information and check-in/out times.
    """
    try:
        export_dir = os.path.join(os.path.dirname(__file__), 'exports')
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = os.path.join(export_dir, f"visitor_logs_{timestamp}.xlsx")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"Available tables: {tables}")
        
        cursor.execute("""
            SELECT 
                l.log_id AS 'Log ID',
                v.name AS 'Visitor Name',
                v.email AS 'Email',
                v.age AS 'Age',
                v.sex AS 'Gender',
                v.address AS 'Address',
                v.id_proof_type AS 'ID Type',
                v.proof_number AS 'ID Number',
                DATE_FORMAT(l.check_in, '%Y-%m-%d %H:%i:%s') AS 'Check In Time',
                DATE_FORMAT(l.check_out, '%Y-%m-%d %H:%i:%s') AS 'Check Out Time',
                IF(l.check_out IS NULL, 'Active', 'Completed') AS 'Status'
            FROM logbook l
            JOIN visitors v ON l.visitor_id = v.visitor_id
            ORDER BY l.check_in DESC
        """)
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not results:
            return jsonify({"error": "No visitor logs found to export"}), 404
            
        import pandas as pd
        df = pd.DataFrame(results)
        
        df.to_excel(export_file, index=False)
            
        return send_file(
            export_file, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True, 
            download_name=f"visitor_logs_{timestamp}.xlsx"
        )
        
    except Exception as e:
        print(f"Export error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/set-auto-backup', methods=['POST'])
@admin_required
def set_auto_backup():
    """Configure automatic backup settings in the database."""
    try:
        data = request.json
        enabled = data.get('enabled', False)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                setting_name VARCHAR(255) PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            INSERT INTO settings (setting_name, setting_value) 
            VALUES ('auto_backup', %s)
            ON DUPLICATE KEY UPDATE setting_value = %s
        """, (str(int(enabled)), str(int(enabled))))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "auto_backup": enabled})
        
    except Exception as e:
        print(f"Setting auto-backup error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/restore-backup', methods=['POST'])
@admin_required
def restore_backup():
    """
    Restores database from uploaded backup file.
    Validates file upload and executes SQL restoration.
    """
    try:
        if 'backup_file' not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
            
        backup_file = request.files['backup_file']
        if backup_file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400
            
        temp_path = os.path.join(os.path.dirname(__file__), 'temp_backup.sql')
        backup_file.save(temp_path)
        
        db_config = {
            "host": "localhost",
            "user": "root",
            "password": "1234",
            "database": "vms"
        }
        
        cmd = [
            'mysql',
            f'--host={db_config["host"]}',
            f'--user={db_config["user"]}',
            f'--password={db_config["password"]}',
            db_config["database"]
        ]
        
        with open(temp_path, 'r') as f:
            process = subprocess.Popen(cmd, stdin=f)
            process.wait()
            
        os.remove(temp_path)
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"Restore error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/staff-login', methods=['GET', 'POST'])
def staff_login():
    """
    Staff login page with email and password authentication.
    Validates staff credentials against database records.
    """
    theme = session.get('theme', 'light')
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("SELECT * FROM staffs WHERE email = %s", (email,))
            staff = cursor.fetchone()
            
            if staff and staff['password'] == password:
                session['staff_logged_in'] = True
                session['staff_id'] = staff['staff_id']
                session['staff_name'] = staff['name']
                
                return redirect(url_for('staff_dashboard'))
            else:
                return render_template('staff_login.html', 
                                       error="Invalid email or password", 
                                       theme=theme)
                
        except Exception as e:
            print(f"Login error: {e}")
            return render_template('staff_login.html', 
                                  error="Database error, please try again", 
                                  theme=theme)
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()
    
    return render_template('staff_login.html', theme=theme)

@app.route('/staff/search-visitors')
@staff_required
def search_visitors():
    """
    API endpoint for staff to search visitors by name.
    Returns visitor information including current check-in status.
    """
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify({"visitors": []})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        search_query = """
        SELECT 
            v.*,
            l.log_id as active_log_id,
            l.check_in as check_in_time,
            CASE WHEN l.check_in IS NOT NULL THEN 1 ELSE 0 END as is_checked_in,
            CASE WHEN l.check_in IS NOT NULL THEN
                CONCAT(
                    FLOOR(TIMESTAMPDIFF(MINUTE, l.check_in, NOW()) / 60),
                    'h ',
                    TIMESTAMPDIFF(MINUTE, l.check_in, NOW()) % 60,
                    'm'
                )
            ELSE '' END as duration
        FROM 
            visitors v
        LEFT JOIN 
            logbook l ON v.visitor_id = l.visitor_id AND l.check_out IS NULL
        WHERE 
            v.name LIKE %s
        ORDER BY 
            v.name
        LIMIT 50
        """
        
        cursor.execute(search_query, (f"%{query}%",))
        visitors = cursor.fetchall()
        
        for visitor in visitors:
            if visitor['check_in_time']:
                visitor['check_in_time'] = visitor['check_in_time'].strftime('%Y-%m-%d %H:%M')
        
        return jsonify({"visitors": visitors})
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/staff/checkin-visitor', methods=['POST'])
@staff_required
def staff_checkin_visitor():
    """
    API endpoint for staff to check in a visitor.
    Creates new logbook entry with current timestamp.
    """
    if 'staff_logged_in' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    data = request.json
    visitor_id = data.get('visitor_id')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT log_id FROM logbook WHERE visitor_id = %s AND check_out IS NULL", (visitor_id,))
        active_session = cursor.fetchone()
        
        if active_session:
            return jsonify({"success": False, "error": "Visitor is already checked in"}), 409
        
        cursor.execute("""
            INSERT INTO logbook (visitor_id, check_in)
            VALUES (%s, NOW())
        """, (visitor_id,))
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"Check-in error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/staff/checkout-visitor', methods=['POST'])
@staff_required
def staff_checkout_visitor():
    """
    API endpoint for staff to check out a visitor.
    Updates existing logbook entry with checkout timestamp.
    """
    if 'staff_logged_in' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    data = request.json
    log_id = data.get('log_id')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE logbook SET check_out = NOW() WHERE log_id = %s", (log_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"success": False, "error": "Log entry not found"}), 404
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"Check-out error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/staff/add-visitor', methods=['POST'])
@staff_required
def staff_add_visitor():
    """
    Add new visitor and automatically check them in.
    Used by staff when registering new visitors on arrival.
    """
    if 'staff_logged_in' not in session:
        return redirect(url_for('staff_login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        name = request.form['name']
        age = request.form['age']
        sex = request.form['sex']
        email = request.form['email']
        address = request.form['address']
        id_proof_type = request.form['id_proof_type']
        proof_number = request.form['proof_number']
        
        cursor.execute("""
            INSERT INTO visitors (name, age, sex, email, address, id_proof_type, proof_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, int(age), sex, email, address, id_proof_type, proof_number))
        
        cursor.execute("SELECT LAST_INSERT_ID()")
        visitor_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO logbook (visitor_id, check_in)
            VALUES (%s, NOW())
        """, (visitor_id,))
        
        conn.commit()
        
    except Exception as e:
        print(f"Add visitor error: {e}")
    
    return redirect(url_for('staff_dashboard'))

@app.route('/staff-logout')
def staff_logout():
    """Staff logout route that clears session data."""
    session.pop('staff_logged_in', None)
    session.pop('staff_id', None)
    session.pop('staff_name', None)
    return redirect(url_for('staff_login'))

@app.route('/staff-dashboard')
@staff_required
def staff_dashboard():
    """
    Main staff dashboard showing active visitor sessions.
    Displays currently checked-in visitors with duration information.
    """
    if 'staff_logged_in' not in session:
        return redirect(url_for('staff_login'))
    
    theme = session.get('theme', 'light')
    staff_id = session.get('staff_id')
    staff_name = session.get('staff_name')
    status = check_db_connection()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                l.log_id,
                l.visitor_id,
                l.check_in,
                v.name as visitor_name,
                CONCAT(
                    FLOOR(TIMESTAMPDIFF(MINUTE, l.check_in, NOW()) / 60),
                    'h ',
                    TIMESTAMPDIFF(MINUTE, l.check_in, NOW()) % 60,
                    'm'
                ) as duration
            FROM logbook l
            JOIN visitors v ON l.visitor_id = v.visitor_id
            WHERE l.check_out IS NULL
            ORDER BY l.check_in DESC
        """
        cursor.execute(query)
        active_sessions = cursor.fetchall()
        
    except Exception as e:
        print(f"Error fetching active sessions: {e}")
        active_sessions = []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
    
    return render_template('staff_dashboard.html', 
                          theme=theme,
                          staff_name=staff_name,
                          active_sessions=active_sessions,
                          status=status)

@app.route('/admin/users/staff/<int:staff_id>/get-password')
@admin_required
def get_staff_password(staff_id):
    """API endpoint to retrieve staff password for editing purposes."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT password FROM staffs WHERE staff_id = %s", (staff_id,))
        result = cursor.fetchone()
        
        if result:
            return jsonify({"password": result['password']})
        else:
            return jsonify({"error": "Staff not found"}), 404
            
    except Exception as e:
        print(f"Error retrieving password: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/admin-logout')
def admin_logout():
    """Admin logout route that clears admin session data."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    """
    Application entry point.
    Runs the Flask development server with debug mode enabled.
    """
    app.run(debug=True)