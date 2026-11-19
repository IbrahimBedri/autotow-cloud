import json
import os
import secrets
import uuid
import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

import produkt_seite   # Seite einer fertigen Produktspule (ohne Flask testbar)

# --- AYARLAR VE BAŞLANGIÇ ---
app = Flask(__name__)

# Render veritabanı adresini al, yoksa yerel test dosyası oluştur
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    db_url = "sqlite:///local_test.db"

# Render için Postgres düzeltmesi
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
# SQLAlchemy 2.1 nimmt bei "postgresql://" den neuen Treiber 'psycopg' (v3), installiert
# ist aber 'psycopg2' (requirements.txt) - der Start scheiterte mit
# "No module named 'psycopg'". Treiber deshalb ausdrücklich nennen.
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Ohne gesetzte SECRET_KEY-Umgebungsvariable wird bei jedem Start ein zufälliger
# Schlüssel erzeugt (kein statisches, im Quellcode sichtbares Geheimnis mehr).
# Nachteil: bestehende Sessions werden beim Neustart ungültig.
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

db = SQLAlchemy(app)

# --- VERİTABANI MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="operator")

class Experiment(db.Model):
    __tablename__ = 'experiment'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    batch_id = db.Column(db.String(50), nullable=False)
    operator = db.Column(db.String(50))
    material = db.Column(db.String(50))
    date = db.Column(db.String(30))
    avg_speed = db.Column(db.Float)
    avg_temp = db.Column(db.Float)
    total_length = db.Column(db.Float)
    status = db.Column(db.String(20))
    logs = db.Column(db.Text) # JSON string olarak saklayabiliriz

class FertigeSpule(db.Model):
    """Öffentliche Daten einer fertigen Produktspule (Etikett-QR zeigt auf /p/<id>)."""
    __tablename__ = 'fertige_spule'
    id = db.Column(db.String(30), primary_key=True)      # z. B. PR-00001-8
    daten = db.Column(db.Text, nullable=False)           # JSON, siehe produkt_seite.py
    csv = db.Column(db.Text)                             # Messdaten, 1 Hz
    aktualisiert = db.Column(db.String(30))

# --- YARDIMCI FONKSİYONLAR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# FIX: Fehlte komplett - '/reset_db_force' und die SQL-Konsole waren nur über
# 'login_required' geschützt (jeder eingeloggte Operator, nicht nur Admins).
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({"error": "Nur Administratoren haben Zugriff auf diese Funktion."}), 403
        return f(*args, **kwargs)
    return decorated_function

# API-Schlüssel für die programmatische Nutzung durch die Desktop-App (kein
# Browser-Login möglich). FIX: '/api/upload' und '/api/register_user' waren
# vorher komplett ungeschützt - jeder im Internet konnte beliebige Datensätze
# einspielen oder sich selbst einen 'admin'-Account anlegen.
CLOUD_API_KEY = os.environ.get('AUTOTOW_CLOUD_API_KEY', '')

def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not CLOUD_API_KEY:
            # Kein Schlüssel konfiguriert -> Endpoint bleibt sicherheitshalber gesperrt
            # (fail closed statt fail open).
            return jsonify({"error": "Server not configured (AUTOTOW_CLOUD_API_KEY missing)"}), 503
        provided_key = request.headers.get('X-API-Key', '')
        if not secrets.compare_digest(provided_key, CLOUD_API_KEY):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- SAYFALAR (ROUTES) ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            error = "Geçersiz kullanıcı adı veya şifre."
            
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Giriş Yap</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f0f2f5; margin: 0; }
            .login-box { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); width: 100%; max-width: 320px; text-align: center; }
            input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            button { width: 100%; padding: 12px; background: #3498db; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
            button:hover { background: #2980b9; }
            .error { color: red; font-size: 14px; margin-bottom: 10px; }
            h2 { margin-top: 0; color: #333; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>AutoTow Cloud</h2>
            {% if error %}<div class="error">{{ error }}</div>{% endif %}
            <form method="post">
                <input type="text" name="username" placeholder="Kullanıcı Adı" required>
                <input type="password" name="password" placeholder="Şifre" required>
                <button type="submit">Giriş Yap</button>
            </form>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# --- DASHBOARD & SQL CONSOLE (BİRLEŞİK) ---
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # 1. SQL Konsol İşlemleri
    query_result = None
    query_error = None
    query_columns = None
    query_msg = None
    sql_query = request.form.get('query', '')

    if request.method == 'POST' and 'btn_sql' in request.form:
        try:
            if not sql_query.strip():
                raise Exception("The query must not be empty.")
            
            # FIX: Die SQL-Konsole erlaubt beliebige Abfragen (auch z.B. das
            # Auslesen aller Passwort-Hashes) - vorher konnte JEDER eingeloggte
            # Benutzer (auch 'operator') sie nutzen, nur DELETE/DROP war auf
            # 'admin' beschränkt. Jetzt ist die gesamte Konsole Admin-only.
            if session.get('role') != 'admin':
                raise Exception("The SQL console is restricted to administrators.")

            # SQLAlchemy ile sorguyu çalıştır (Render için uygun yöntem)
            result_proxy = db.session.execute(text(sql_query))

            if sql_query.strip().upper().startswith("SELECT"):
                query_result = result_proxy.fetchall()
                query_columns = result_proxy.keys()
            else:
                db.session.commit()
                query_msg = f"✅ İşlem Başarılı! Etkilenen satır: {result_proxy.rowcount}"
                
        except Exception as e:
            db.session.rollback()
            query_error = str(e)

    # 2. Deney Listesini Çek
    try:
        # SQLAlchemy ORM kullanarak verileri çekiyoruz
        experiments = Experiment.query.order_by(Experiment.id.desc()).all()
    except Exception as fehler:
        print(f"[SERVER] ERROR: could not read the experiments from the database: {fehler}")
        experiments = []

    # 3. HTML Arayüzü
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AutoTow Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; }
            .card { background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); padding: 20px; margin-bottom: 20px; }
            h1, h2 { color: #2c3e50; margin-top: 0; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
            th { background-color: #f8f9fa; color: #7f8c8d; font-weight: 600; font-size: 14px; }
            tr:hover { background-color: #f1f1f1; }
            .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
            .badge-ok { background: #d4edda; color: #155724; }
            .badge-err { background: #f8d7da; color: #721c24; }
            
            /* SQL Konsol Stilleri */
            details { background: #2c3e50; color: white; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
            summary { cursor: pointer; font-weight: bold; outline: none; }
            .sql-box { margin-top: 15px; padding: 10px; background: #34495e; border-radius: 5px; }
            textarea { width: 100%; height: 80px; background: #2c3e50; color: #ecf0f1; border: 1px solid #7f8c8d; padding: 10px; font-family: monospace; }
            .btn-run { background: #3498db; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; margin-top: 10px; }
            .error-box { background: #e74c3c; color: white; padding: 10px; border-radius: 4px; margin-top: 10px; }
            .success-box { background: #27ae60; color: white; padding: 10px; border-radius: 4px; margin-top: 10px; }
            
            .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .logout { color: #e74c3c; text-decoration: none; font-weight: bold; }
            a.btn-view { text-decoration: none; color: #3498db; font-weight: bold; }
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
                        <textarea name="query" placeholder="SELECT * FROM experiment WHERE operator='admin'...">{{ sql_query }}</textarea>
                        <br>
                        <button type="submit" name="btn_sql" class="btn-run">Sorguyu Çalıştır</button>
                    </form>

                    {% if query_error %}<div class="error-box">HATA: {{ query_error }}</div>{% endif %}
                    {% if query_msg %}<div class="success-box">{{ query_msg }}</div>{% endif %}

                    {% if query_result %}
                        <div style="overflow-x: auto; background: white; margin-top: 10px; border-radius: 4px;">
                            <table style="color: #333;">
                                <thead>
                                    <tr>
                                        {% for col in query_columns %}<th>{{ col }}</th>{% endfor %}
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for row in query_result %}
                                    <tr>
                                        {% for cell in row %}<td>{{ cell }}</td>{% endfor %}
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
                                <th>Tarih</th>
                                <th>Uzunluk (m)</th>
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
                                <td>{{ exp.date }}</td>
                                <td>{{ exp.total_length }}</td>
                                <td><span class="badge {% if exp.status == 'COMPLETED' %}badge-ok{% else %}badge-err{% endif %}">{{ exp.status }}</span></td>
                                <td><a href="/view/{{ exp.uuid }}" class="btn-view" target="_blank">Rapor →</a></td>
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

# --- API UÇLARI (Programdan Veri Almak İçin) ---
@app.route('/api/upload', methods=['POST'])
@api_key_required
def upload_data():
    data = request.json
    try:
        # Önce bu UUID ile kayıt var mı bakalım
        existing = Experiment.query.filter_by(uuid=data['uuid']).first()
        if existing:
            return jsonify({"message": "Data already exists"}), 200

        new_exp = Experiment(
            uuid=data['uuid'],
            batch_id=data.get('batch_id', 'UNKNOWN'),
            operator=data.get('operator', 'Unknown'),
            material=data.get('material', 'Generic'),
            date=str(data.get('date')),
            avg_speed=data.get('avg_speed', 0.0),
            avg_temp=data.get('avg_temp', 0.0),
            total_length=data.get('total_length', 0.0),
            status=data.get('status', 'COMPLETED'),
            logs=str(data.get('logs', []))
        )
        db.session.add(new_exp)
        db.session.commit()
        return jsonify({"message": "Upload successful"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/register_user', methods=['POST'])
@api_key_required
def api_register_user():
    data = request.json
    try:
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'operator')

        if User.query.filter_by(username=username).first():
            return jsonify({"message": "User already exists"}), 400

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- FERTIGE PRODUKTSPULEN (öffentlich lesbar, Upload nur mit API-Schlüssel) ---
@app.route('/api/product', methods=['POST'])
@api_key_required
def api_product():
    nutz = request.get_json(silent=True) or {}
    try:
        daten = produkt_seite.nutzdaten_pruefen(nutz.get('daten'), nutz.get('csv'))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    eintrag = db.session.get(FertigeSpule, daten['id'])
    if eintrag is None:
        eintrag = FertigeSpule(id=daten['id'])
        db.session.add(eintrag)
    eintrag.daten = json.dumps(daten)
    # Messdaten nur ersetzen, wenn neue mitkommen (ein Upload ohne CSV löscht sie nicht)
    if nutz.get('csv'):
        eintrag.csv = nutz['csv']
    eintrag.aktualisiert = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()
    return jsonify({"message": "Product saved", "id": daten['id']}), 200

@app.route('/p/<produkt_id>')
def produkt_seite_anzeigen(produkt_id):
    eintrag = db.session.get(FertigeSpule, produkt_id) if produkt_seite.id_gueltig(produkt_id) else None
    if eintrag is None:
        return "Product not found", 404
    return produkt_seite.seite_html(json.loads(eintrag.daten), bool(eintrag.csv))

@app.route('/p/<produkt_id>/data.csv')
def produkt_daten(produkt_id):
    eintrag = db.session.get(FertigeSpule, produkt_id) if produkt_seite.id_gueltig(produkt_id) else None
    if eintrag is None or not eintrag.csv:
        return "No data", 404
    return Response(eintrag.csv, mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment; filename={produkt_id}.csv"})

# --- RAPOR GÖRÜNTÜLEME ---
@app.route('/view/<uuid_val>')
def view_report(uuid_val):
    exp = Experiment.query.filter_by(uuid=uuid_val).first()
    if not exp:
        return "Rapor bulunamadı", 404
        
    html = """
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
                <h1>AutoTow Üretim Raporu</h1>
                <p>ID: {{ exp.uuid }}</p>
            </div>
            <div class="content">
                <div class="row"><span>Batch ID:</span> <span>{{ exp.batch_id }}</span></div>
                <div class="row"><span>Malzeme:</span> <span>{{ exp.material }}</span></div>
                <div class="row"><span>Operatör:</span> <span>{{ exp.operator }}</span></div>
                <div class="row"><span>Tarih:</span> <span>{{ exp.date }}</span></div>
                <hr>
                <div class="row"><span style="font-weight:bold">Toplam Uzunluk:</span> <span style="font-weight:bold; color:#2c3e50">{{ exp.total_length }} m</span></div>
                <div class="row"><span>Ort. Hız:</span> <span>{{ exp.avg_speed }} m/min</span></div>
                <div class="row"><span>Ort. Sıcaklık:</span> <span>{{ exp.avg_temp }} °C</span></div>
                
                <div class="status-box">{{ exp.status }}</div>
                <a href="/login" class="login-link">🔐 Yönetici Girişi</a>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, exp=exp)

# --- BAŞLANGIÇTA ÇALIŞACAK KODLAR ---
# Passwort des ersten Administrators ('master'). Vorher stand hier '1234' als
# Rückfallwert - ein öffentlich im Quellcode lesbares Passwort für einen
# öffentlich erreichbaren Server. Ohne gesetzte Umgebungsvariable wird jetzt ein
# zufälliges erzeugt und EINMAL beim Anlegen ins Server-Log geschrieben.
# Betrifft nur das erstmalige Anlegen: Ein bereits vorhandener 'master' behält
# sein Passwort.
_MASTER_AUS_UMGEBUNG = os.environ.get('AUTOTOW_CLOUD_ADMIN_PASSWORD')
DEFAULT_MASTER_PASSWORD = _MASTER_AUS_UMGEBUNG or secrets.token_urlsafe(12)

with app.app_context():
    db.create_all()
    # Varsayılan Admin (Sadece hiç kullanıcı yoksa oluşturulur)
    if not User.query.filter_by(username='master').first():
        hashed = generate_password_hash(DEFAULT_MASTER_PASSWORD)
        db.session.add(User(username='master', password_hash=hashed, role='admin'))
        db.session.commit()
        if _MASTER_AUS_UMGEBUNG:
            print("[SERVER] Default admin created: master / (AUTOTOW_CLOUD_ADMIN_PASSWORD)")
        else:
            print("[SERVER] WARNING: AUTOTOW_CLOUD_ADMIN_PASSWORD is not set. "
                  f"Admin 'master' created with the generated password: {DEFAULT_MASTER_PASSWORD}")

# Nur per POST: Als GET konnte schon ein einziger Link (z.B. in einer E-Mail
# oder als Bild in einer fremden Seite), den ein angemeldeter Administrator
# öffnet, die komplette Datenbank löschen.
@app.route('/reset_db_force', methods=['POST'])
@admin_required
def reset_db_force():
    # DİKKAT: Bu işlem Cloud üzerindeki tüm verileri siler ve tabloyu yeniden yaratır.
    # FIX: War vorher komplett ungeschützt (keine Authentifizierung) - jeder, der
    # die URL kannte, konnte per einfachem GET-Request die gesamte Cloud-Datenbank löschen.
    try:
        db.drop_all()   # Eski tabloları sil
        db.create_all() # Yeni sütunlarla (logs dahil) tekrar oluşturr
        
        # Admin kullanıcısını tekrar ekle
        if not User.query.filter_by(username='master').first():
            hashed = generate_password_hash(DEFAULT_MASTER_PASSWORD)
            db.session.add(User(username='master', password_hash=hashed, role='admin'))
            db.session.commit()
            
        return "✅ BAŞARILI: Veritabanı sıfırlandı, 'logs' sütunu eklendi ve Admin oluşturuldu!"
    except Exception as e:
        return f"❌ HATA: {str(e)}"        

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)