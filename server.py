# ZORUNLU GUNCELLEME V1
# Dosya: server.py (Full Sync Versiyon)
import os
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json
import uuid

app = Flask(__name__)

# --- AYARLAR ---
db_url = os.environ.get('DATABASE_URL')

# Eğer Cloud adresi bulunamazsa (yani senin bilgisayarındaysak), yerel bir dosya kullan
if not db_url:
    db_url = "sqlite:///local_test.db"  # Bilgisayarında bu isimde dosya oluşturur
    print("⚠️ UYARI: Cloud veritabanı bulunamadı, yerel 'local_test.db' kullanılıyor.")

# SQLAlchemy 'postgres://' düzeltmesi (Render için)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "gizli_anahtar_super_secure"

db = SQLAlchemy(app)

# --- VERİTABANI MODELLERİ ---

# 1. KULLANICILAR TABLOSU (YENİ)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="operator") # admin veya operator

# 2. DENEYLER TABLOSU
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
    detailed_logs = db.Column(db.Text, nullable=True) 

# Veritabanını oluştur
with app.app_context():
    db.create_all()
    # Varsayılan Admin Yoksa Oluştur (İlk giriş için)
    if not User.query.filter_by(username="admin").first():
        hashed_pw = generate_password_hash("admin123")
        admin = User(username="admin", password_hash=hashed_pw, role="admin")
        db.session.add(admin)
        db.session.commit()
        print("✅ Varsayılan Admin Kullanıcısı Oluşturuldu (admin / admin123)")

# --- API (WINDOWS APP İÇİN KAPILAR) ---

# A. YENİ KULLANICI KAYDETME (Windows App Buraya Gönderecek)
@app.route('/api/register_user', methods=['POST'])
def register_user():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'operator')

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "User already exists"}), 400

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({"status": "success", "username": username}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# B. VERİ YÜKLEME
@app.route('/api/upload', methods=['POST'])
def upload_data():
    try:
        data = request.json
        unique_id = data.get('uuid')
        if not unique_id: unique_id = str(uuid.uuid4())[:8]
        
        # Eğer bu ID zaten varsa güncelle, yoksa yeni ekle
        existing_exp = Experiment.query.filter_by(uuid=unique_id).first()
        if existing_exp:
            # Güncelleme mantığı (şimdilik pass geçiyoruz, duplicate olmasın diye)
            return jsonify({"status": "exists", "id": unique_id}), 200

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
            detailed_logs=json.dumps(data.get('logs', []))
        )
        db.session.add(new_exp)
        db.session.commit()
        return jsonify({"status": "success", "id": unique_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- WEB ARAYÜZÜ ---

# 1. LOGIN SAYFASI
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_HTML, error="Hatalı Kullanıcı Adı veya Şifre!")
            
    return render_template_string(LOGIN_HTML)

# 2. DASHBOARD
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    experiments = Experiment.query.order_by(Experiment.id.desc()).all()
    return render_template_string(DASHBOARD_HTML, experiments=experiments, user=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/view/<uuid>')
def view_report(uuid):
    exp = Experiment.query.filter_by(uuid=uuid).first()
    if not exp: return "Bulunamadı", 404
    return render_template_string(PUBLIC_REPORT_HTML, exp=exp)


# --- HTML ŞABLONLARI ---

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
        <h2>AutoTow Login</h2>
        <input type="text" name="username" placeholder="Kullanıcı Adı" required>
        <input type="password" name="password" placeholder="Şifre" required>
        <button type="submit">Giriş Yap</button>
        {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
    </form>
</body>
</html>
"""

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
        <h3 style="margin:0; padding-left:10px;">🚀 AutoTow Cloud | {{ user }}</h3>
        <a href="/logout" class="logout">Çıkış Yap</a>
    </div>
    <div class="container">
        <h2>Üretim Geçmişi (Production History)</h2>
        <table>
            <thead>
                <tr>
                    <th>Tarih</th>
                    <th>Batch ID</th>
                    <th>Operatör</th>
                    <th>Durum</th>
                    <th>Detay</th>
                </tr>
            </thead>
            <tbody>
                {% for exp in experiments %}
                <tr>
                    <td>{{ exp.date }}</td>
                    <td>{{ exp.batch_id }}</td>
                    <td>{{ exp.operator }}</td>
                    <td style="color: {{ 'green' if exp.status=='COMPLETED' else 'orange' }}">{{ exp.status }}</td>
                    <td><a href="/view/{{ exp.uuid }}" class="btn">Raporu Gör</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

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
        .content { padding: 20px; }
        .row { display: flex; justify-content: space-between; border-bottom: 1px solid #eee; padding: 12px 0; }
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
            <div class="row"><span>Batch:</span> <span>{{ exp.batch_id }}</span></div>
            <div class="row"><span>Material:</span> <span>{{ exp.material }}</span></div>
            <div class="row"><span>Operator:</span> <span>{{ exp.operator }}</span></div>
            <div class="row"><span>Date:</span> <span>{{ exp.date }}</span></div>
            <hr>
            <div class="row"><span>Speed:</span> <span>{{ exp.avg_speed }} m/min</span></div>
            <div class="status-box">{{ exp.status }}</div>
            <a href="/login" class="login-link">🔐 Yönetici Girişi</a>
        </div>
    </div>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
