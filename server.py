# Dosya: server.py (Full Sync Versiyon)
import os
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json
import uuid
import sqlite3
from functools import wraps
from sqlalchemy import text

app = Flask(__name__)

# --- AYARLAR ---
db_url = os.environ.get('DATABASE_URL')

# Eğer Cloud adresi bulunamazsa (yani senin bilgisayarındaysak), yerel bir dosya kullan1
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






# 1. Veritabanı Bağlantı Fonksiyonu
def get_db_connection():
    # Veritabanı dosya adının doğru olduğundan emin ol
    conn = sqlite3.connect('autotow_system.db') 
    conn.row_factory = sqlite3.Row
    return conn

# 2. Giriş Zorunluluğu (login_required) Tanımlaması
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Eğer kullanıcı giriş yapmamışsa login sayfasına at
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # --- 1. SQL KONSOL MANTIĞI ---
    query_result = None
    query_error = None
    query_columns = None
    query_msg = None
    sql_query = request.form.get('query', '')

    # Eğer "Sorguyu Çalıştır" butonuna basıldıysa
    if request.method == 'POST' and 'btn_sql' in request.form:
        try:
            if not sql_query.strip():
                raise Exception("Sorgu boş olamaz!")

            # Güvenlik: Silme işlemini sadece admin yapabilsin
            if ("DELETE" in sql_query.upper() or "DROP" in sql_query.upper()) and session.get('username') != 'admin':
                raise Exception("Silme işlemi için yetkiniz yok!")

            # SQLAlchemy ile sorguyu çalıştır (En güvenli yöntem)
            result_proxy = db.session.execute(text(sql_query))

            if sql_query.strip().upper().startswith("SELECT"):
                # Sonuçları al
                query_result = result_proxy.fetchall()
                query_columns = result_proxy.keys() # Sütun isimleri
            else:
                # UPDATE/INSERT ise kaydet
                db.session.commit()
                query_msg = f"✅ İşlem Başarılı! Etkilenen satır: {result_proxy.rowcount}"
        except Exception as e:
            db.session.rollback() # Hata olursa geri al
            query_error = str(e)

    # --- 2. STANDART DENEY LİSTESİ (Her zaman görünür) ---
    # SQLAlchemy kullanarak veriyi çekiyoruz
    try:
        experiments_proxy = db.session.execute(text('SELECT * FROM experiments ORDER BY id DESC'))
        experiments = experiments_proxy.fetchall()
    except:
        experiments = [] # Tablo henüz yoksa hata vermesin

    # --- 3. HTML ARAYÜZÜ ---
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AutoTow Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; }
            
            /* Kart Tasarımı */
            .card { background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); padding: 20px; margin-bottom: 20px; }
            h1, h2 { color: #2c3e50; margin-top: 0; }
            
            /* Tablo Tasarımı */
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
            th { background-color: #f8f9fa; color: #7f8c8d; font-weight: 600; font-size: 14px; }
            tr:hover { background-color: #f1f1f1; }
            
            /* Status Renkleri */
            .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
            .badge-ok { background: #d4edda; color: #155724; }
            .badge-err { background: #f8d7da; color: #721c24; }

            /* SQL Konsol Alanı (Açılır Kapanır) */
            details { background: #2c3e50; color: white; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
            summary { cursor: pointer; font-weight: bold; outline: none; }
            .sql-box { margin-top: 15px; padding: 10px; background: #34495e; border-radius: 5px; }
            textarea { width: 100%; height: 80px; background: #2c3e50; color: #ecf0f1; border: 1px solid #7f8c8d; padding: 10px; font-family: monospace; }
            .btn-run { background: #3498db; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; margin-top: 10px; }
            .btn-run:hover { background: #2980b9; }
            
            .error-box { background: #e74c3c; color: white; padding: 10px; border-radius: 4px; margin-top: 10px; }
            .success-box { background: #27ae60; color: white; padding: 10px; border-radius: 4px; margin-top: 10px; }
            
            /* Linkler */
            a.btn-view { text-decoration: none; color: #3498db; font-weight: bold; }
            .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .logout { color: #e74c3c; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-bar">
                <h1>🎛️ Yönetim Paneli</h1>
                <a href="/logout" class="logout">Çıkış Yap</a>
            </div>

            <details {% if query_result or query_error or query_msg %}open{% endif %}>
                <summary>🛠️ Gelişmiş Veritabanı Sorgusu (SQL)</summary>
                <div class="sql-box">
                    <form method="POST">
                        <textarea name="query" placeholder="SELECT * FROM experiments WHERE operator='admin'...">{{ sql_query }}</textarea>
                        <br>
                        <button type="submit" name="btn_sql" class="btn-run">Sorguyu Çalıştır</button>
                    </form>

                    {% if query_error %}
                        <div class="error-box">HATA: {{ query_error }}</div>
                    {% endif %}
                    {% if query_msg %}
                        <div class="success-box">{{ query_msg }}</div>
                    {% endif %}

                    {% if query_result %}
                        <div style="overflow-x: auto; background: white; margin-top: 10px; border-radius: 4px;">
                            <table style="color: #333;">
                                <thead>
                                    <tr>
                                        {% for col in query_columns %}
                                        <th>{{ col }}</th>
                                        {% endfor %}
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for row in query_result %}
                                    <tr>
                                        {% for cell in row %}
                                        <td>{{ cell }}</td>
                                        {% endfor %}
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    {% endif %}
                </div>
            </details>

            <div class="card">
                <h2>📊 Son Deneyler</h2>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Batch</th>
                                <th>Malzeme</th>
                                <th>Operatör</th>
                                <th>Durum</th>
                                <th>İşlem</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for exp in experiments %}
                            <tr>
                                <td>{{ exp.id }}</td>
                                <td>{{ exp.batch_id }}</td>
                                <td>{{ exp.material }}</td>
                                <td>{{ exp.operator }}</td>
                                <td>
                                    <span class="badge {% if exp.status == 'COMPLETED' %}badge-ok{% else %}badge-err{% endif %}">
                                        {{ exp.status }}
                                    </span>
                                </td>
                                <td><a href="/view/{{ exp.uuid }}" class="btn-view" target="_blank">Raporu Gör →</a></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, experiments=experiments, 
                                  query_result=query_result, query_error=query_error, 
                                  query_columns=query_columns, sql_query=sql_query, query_msg=query_msg)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
