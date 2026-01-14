# Dosya: server.py (AutoTow Cloud Portal - PostgreSQL Sürümü)
import os
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import uuid  # Eksik olmasın diye ekledik

app = Flask(__name__)

# --- AYARLAR ---
# Render'daki veritabanı adresini alıyoruz
db_url = os.environ.get('DATABASE_URL')
# SQLAlchemy 'postgres://' formatını sevmez, onu düzeltiyoruz
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "gizli_anahtar_autotow_secure" # Session güvenliği için

db = SQLAlchemy(app)

# --- VERİTABANI MODELİ (TABLO TASARIMI) ---
# DİKKAT: Eski koddaki TÜM veriler burada sütun olarak var.
class Experiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(50), unique=True, nullable=False)
    batch_id = db.Column(db.String(100))
    operator = db.Column(db.String(100))
    material = db.Column(db.String(100))
    date = db.Column(db.String(50))
    avg_speed = db.Column(db.Float)
    avg_temp = db.Column(db.Float)
    total_length = db.Column(db.Float)
    status = db.Column(db.String(50))
    
    # İlerde grafik verisi gelirse buraya koyacağız (şimdilik boş kalabilir)
    detailed_logs = db.Column(db.Text, nullable=True) 

    def __repr__(self):
        return f'<Experiment {self.batch_id}>'

# Veritabanını oluştur (İlk çalışmada tabloları kurar)
with app.app_context():
    db.create_all()

# --- HTML TASARIMLARI ---

# 1. HALKA AÇIK RAPOR (Senin eski tasarımına sadık kalındı)
PUBLIC_REPORT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AutoTow Report</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #f0f2f5; padding: 20px; margin: 0; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: #2c3e50; color: white; padding: 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .header p { margin: 5px 0 0; opacity: 0.8; font-size: 14px; }
        .content { padding: 20px; }
        .row { display: flex; justify-content: space-between; border-bottom: 1px solid #eee; padding: 12px 0; }
        .label { font-weight: 600; color: #7f8c8d; }
        .value { font-weight: 400; color: #2c3e50; }
        .status-box { text-align: center; padding: 15px; background: #e8f5e9; color: #2e7d32; border-radius: 8px; margin-top: 20px; font-weight: bold; }
        .login-link { display: block; text-align: center; margin-top: 20px; color: #3498db; text-decoration: none; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AutoTow Production Report</h1>
            <p>ID: {{ exp.uuid }}</p>
        </div>
        <div class="content">
            <div class="row"><span class="label">Batch Name:</span> <span class="value">{{ exp.batch_id }}</span></div>
            <div class="row"><span class="label">Operator:</span> <span class="value">{{ exp.operator }}</span></div>
            <div class="row"><span class="label">Material:</span> <span class="value">{{ exp.material }}</span></div>
            <div class="row"><span class="label">Date:</span> <span class="value">{{ exp.date }}</span></div>
            
            <hr style="border:0; border-top:1px dashed #ccc; margin: 20px 0;">
            
            <div class="row"><span class="label">Avg. Speed:</span> <span class="value">{{ exp.avg_speed }} m/min</span></div>
            <div class="row"><span class="label">Avg. Temp:</span> <span class="value">{{ exp.avg_temp }} °C</span></div>
            <div class="row"><span class="label">Total Length:</span> <span class="value">{{ exp.total_length }} m</span></div>
            
            <div class="status-box">STATUS: {{ exp.status }}</div>
            
            <a href="/login" class="login-link">🔐 Engineer Access (Full History)</a>
        </div>
    </div>
</body>
</html>
"""

# 2. ADMIN DASHBOARD (Yeni Özellik)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AutoTow Portal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #eceff1; margin: 0; }
        .navbar { background: #263238; color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; }
        .container { padding: 20px; max-width: 1000px; margin: 0 auto; }
        table { width: 100%; background: white; border-collapse: collapse; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        th, td { padding: 15px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #37474f; color: white; }
        tr:hover { background-color: #f5f5f5; }
        .btn { padding: 5px 10px; background: #0288d1; color: white; text-decoration: none; border-radius: 4px; font-size: 14px; }
        .logout { color: #ffcdd2; text-decoration: none; margin-right: 20px; }
    </style>
</head>
<body>
    <div class="navbar">
        <h3 style="margin:0; padding-left:10px;">🚀 AutoTow Cloud Portal</h3>
        <a href="/logout" class="logout">Logout</a>
    </div>
    <div class="container">
        <h2>Production History</h2>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Batch ID</th>
                    <th>Material</th>
                    <th>Status</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {% for exp in experiments %}
                <tr>
                    <td>{{ exp.date }}</td>
                    <td>{{ exp.batch_id }}</td>
                    <td>{{ exp.material }}</td>
                    <td style="color: {{ 'green' if exp.status=='COMPLETED' else 'orange' }}">{{ exp.status }}</td>
                    <td><a href="/view/{{ exp.uuid }}" class="btn">View</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

# 3. LOGIN SAYFASI
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { display: flex; justify-content: center; align-items: center; height: 100vh; background: #cfd8dc; font-family: sans-serif; margin:0; }
        form { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); text-align: center; width: 300px; }
        input { padding: 10px; margin: 10px 0; width: 90%; display: block; margin-left: auto; margin-right: auto; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 10px 20px; background: #263238; color: white; border: none; cursor: pointer; border-radius: 5px; width: 96%; margin-top: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <form method="POST">
        <h2>Engineer Access</h2>
        <input type="password" name="password" placeholder="Enter Password" required>
        <button type="submit">Login</button>
        {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
    </form>
</body>
</html>
"""

# --- ROUTES (YÖNLENDİRMELER) ---

# 1. VERİ KAYDETME (Windows App Buraya Gönderir)
@app.route('/api/upload', methods=['POST'])
def upload_data():
    try:
        data = request.json
        # Windows App'ten gelen verileri alıyoruz
        unique_id = data.get('uuid')
        
        # UUID yoksa oluştur (Eski koddaki mantık)
        if not unique_id:
            unique_id = str(uuid.uuid4())[:8]
        
        # Veritabanı Nesnesi Oluştur
        new_exp = Experiment(
            uuid=unique_id,
            batch_id=data.get('batch_id'),
            operator=data.get('operator'),
            material=data.get('material'),
            date=data.get('date'),
            avg_speed=data.get('avg_speed'),
            avg_temp=data.get('avg_temp'),
            total_length=data.get('total_length'),
            status=data.get('status'),
            detailed_logs=json.dumps(data.get('logs', [])) # İlerde detaylı log gelirse sakla
        )
        
        db.session.add(new_exp)
        db.session.commit()
        
        print(f"✅ DB KAYDI BAŞARILI: {new_exp.batch_id} (ID: {unique_id})")
        return jsonify({"status": "success", "id": unique_id}), 200
    except Exception as e:
        print(f"❌ DB HATASI: {e}")
        return jsonify({"error": str(e)}), 500

# 2. RAPOR GÖRÜNTÜLEME (QR Kod Burayı Açar)
@app.route('/view/<uuid>')
def view_report(uuid):
    # Veritabanından o ID'ye sahip deneyi bul
    exp = Experiment.query.filter_by(uuid=uuid).first()
    
    if not exp:
        return """
        <div style='text-align:center; padding:50px; font-family:Arial;'>
            <h1 style='color:red;'>⚠️ Report Not Found</h1>
            <p>Database refreshed. Old data might be gone.</p>
        </div>
        """, 404
        
    return render_template_string(PUBLIC_REPORT_HTML, exp=exp)

# 3. GİRİŞ YAPMA (Login)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        # ŞİFRE: admin123 (Burayı ilerde değiştirebilirsin)
        if password == "admin123": 
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_HTML, error="Wrong Password!")
    return render_template_string(LOGIN_HTML)

# 4. YÖNETİCİ PANELİ (Dashboard)
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Tüm deneyleri tarihe göre tersten (en yeni en üstte) getir
    experiments = Experiment.query.order_by(Experiment.id.desc()).all()
    return render_template_string(DASHBOARD_HTML, experiments=experiments)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def home():
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Render'da port otomatiktir ama lokalde 5001 kullanır
    app.run(host='0.0.0.0', port=5001)
