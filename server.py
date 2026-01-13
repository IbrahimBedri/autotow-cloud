# Dosya: local_cloud/server.py
from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)
DB_FILE = "veritabani.json"

print("☁️  GÜÇLENDİRİLMİŞ LOCAL CLOUD BAŞLATILIYOR...")

# --- YARDIMCI FONKSİYONLAR (Dosya Okuma/Yazma) ---
def veri_yukle():
    """JSON dosyasından verileri okur."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def veri_kaydet(veri):
    """Verileri JSON dosyasına yazar."""
    mevcut = veri_yukle()
    # Yeni veriyi ekle/güncelle
    mevcut.update(veri)
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(mevcut, f, ensure_ascii=False, indent=4)

# 1. VERİ KARŞILAMA KAPISI
@app.route('/api/upload', methods=['POST'])
def upload_data():
    try:
        data = request.json
        unique_id = data.get('uuid')
        
        if not unique_id:
            # Eğer UUID gelmediyse biz oluşturalım (Hata vermesin)
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            data['uuid'] = unique_id
            
        # Veriyi DOSYAYA kaydet
        veri_kaydet({unique_id: data})
        
        print(f"\n✅ YENİ VERİ KAYDEDİLDİ! ID: {unique_id}")
        return jsonify({"status": "success", "id": unique_id}), 200
    except Exception as e:
        print(f"❌ HATA: {e}")
        return jsonify({"error": str(e)}), 500

# 2. RAPOR GÖRÜNTÜLEME KAPISI
@app.route('/view/<uuid>')
def view_report(uuid):
    tum_veriler = veri_yukle()
    data = tum_veriler.get(uuid)
    
    if not data:
        return f"""
        <div style='text-align:center; padding:50px; font-family:Arial;'>
            <h1 style='color:red;'>⚠️ Rapor Bulunamadı</h1>
            <p>Aradığınız ID: <b>{uuid}</b> veritabanında yok.</p>
            <p>Sunucu sıfırlanmış olabilir veya ID yanlıştır.</p>
        </div>
        """, 404
        
    # HTML Raporu
    html = f"""
    <html>
        <head>
            <title>AutoTow Report - {uuid}</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .header p {{ margin: 5px 0 0; opacity: 0.8; font-size: 14px; }}
                .content {{ padding: 20px; }}
                .row {{ display: flex; justify-content: space-between; border-bottom: 1px solid #eee; padding: 12px 0; }}
                .row:last-child {{ border-bottom: none; }}
                .label {{ font-weight: 600; color: #7f8c8d; }}
                .value {{ font-weight: 400; color: #2c3e50; }}
                .status-box {{ text-align: center; padding: 15px; background: #e8f5e9; color: #2e7d32; border-radius: 8px; margin-top: 20px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>AutoTow Üretim Raporu</h1>
                    <p>ID: {uuid}</p>
                </div>
                <div class="content">
                    <div class="row"><span class="label">Batch Name:</span> <span class="value">{data.get('batch_id', '-')}</span></div>
                    <div class="row"><span class="label">Operator:</span> <span class="value">{data.get('operator', '-')}</span></div>
                    <div class="row"><span class="label">Malzeme:</span> <span class="value">{data.get('material', '-')}</span></div>
                    <div class="row"><span class="label">Tarih:</span> <span class="value">{data.get('date', '-')}</span></div>
                    
                    <hr style="border:0; border-top:1px dashed #ccc; margin: 20px 0;">
                    
                    <div class="row"><span class="label">Ort. Hız:</span> <span class="value">{data.get('avg_speed', 0)} m/min</span></div>
                    <div class="row"><span class="label">Ort. Sıcaklık:</span> <span class="value">{data.get('avg_temp', 0)} °C</span></div>
                    <div class="row"><span class="label">Toplam Uzunluk:</span> <span class="value">{data.get('total_length', 0)} m</span></div>
                    
                    <div class="status-box">
                        DURUM: {data.get('status', 'OK')}
                    </div>
                </div>
            </div>
        </body>
    </html>
    """
    return html

# 3. KONTROL KAPISI (Veri var mı diye bakmak için)
@app.route('/debug')
def debug_db():
    return jsonify(veri_yukle())

if __name__ == '__main__':
    # AirPlay çakışmasını önlemek için 5001 yapıyoruz
    app.run(host='0.0.0.0', port=5001, debug=True)