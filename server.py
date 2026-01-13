# Dosya: local_cloud/server.py
from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)
DB_FILE = "veritabani.json"

print("☁️  ENHANCED CLOUD SERVER STARTED...")

# --- HELPER FUNCTIONS ---
def load_data():
    """Reads data from JSON file."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    """Writes data to JSON file."""
    current = load_data()
    current.update(data)
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(current, f, ensure_ascii=False, indent=4)

# 1. DATA UPLOAD ENDPOINT
@app.route('/api/upload', methods=['POST'])
def upload_data():
    try:
        data = request.json
        unique_id = data.get('uuid')
        
        if not unique_id:
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            data['uuid'] = unique_id
            
        save_data({unique_id: data})
        
        print(f"\n✅ NEW DATA SAVED! ID: {unique_id}")
        return jsonify({"status": "success", "id": unique_id}), 200
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"error": str(e)}), 500

# 2. REPORT VIEW ENDPOINT (ENGLISH)
@app.route('/view/<uuid>')
def view_report(uuid):
    all_data = load_data()
    data = all_data.get(uuid)
    
    if not data:
        return f"""
        <div style='text-align:center; padding:50px; font-family:Arial;'>
            <h1 style='color:red;'>⚠️ Report Not Found</h1>
            <p>The ID you are looking for: <b>{uuid}</b> was not found.</p>
            <p>The server might have been reset or the ID is incorrect.</p>
        </div>
        """, 404
        
    # HTML Report (English)
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
                    <h1>AutoTow Production Report</h1>
                    <p>ID: {uuid}</p>
                </div>
                <div class="content">
                    <div class="row"><span class="label">Batch Name:</span> <span class="value">{data.get('batch_id', '-')}</span></div>
                    <div class="row"><span class="label">Operator:</span> <span class="value">{data.get('operator', '-')}</span></div>
                    <div class="row"><span class="label">Material:</span> <span class="value">{data.get('material', '-')}</span></div>
                    <div class="row"><span class="label">Date:</span> <span class="value">{data.get('date', '-')}</span></div>
                    
                    <hr style="border:0; border-top:1px dashed #ccc; margin: 20px 0;">
                    
                    <div class="row"><span class="label">Avg. Speed:</span> <span class="value">{data.get('avg_speed', 0)} m/min</span></div>
                    <div class="row"><span class="label">Avg. Temp:</span> <span class="value">{data.get('avg_temp', 0)} °C</span></div>
                    <div class="row"><span class="label">Total Length:</span> <span class="value">{data.get('total_length', 0)} m</span></div>
                    
                    <div class="status-box">
                        STATUS: {data.get('status', 'OK')}
                    </div>
                </div>
            </div>
        </body>
    </html>
    """
    return html

# 3. DEBUG ENDPOINT
@app.route('/debug')
def debug_db():
    return jsonify(load_data())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
