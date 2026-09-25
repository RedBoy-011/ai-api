import os
import sys
import json
import traceback
import subprocess
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# تعیین مسیر دقیق اجرایی و پوشه templates
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    # بررسی هر دو مسیر احتمالی templates در ساختار جدید PyInstaller
    internal_templates = os.path.join(base_dir, '_internal', 'templates')
    root_templates = os.path.join(base_dir, 'templates')
    template_folder = internal_templates if os.path.exists(internal_templates) else root_templates
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_folder = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_folder)
app.secret_key = "infrastructure_secret_key_secure_session"

# ثبت لاگ خطا در صورت بروز مشکل
def log_crash(e):
    with open(os.path.join(base_dir, "crash_log.txt"), "a", encoding="utf-8") as f:
        f.write(f"CRASH: {str(e)}\n{traceback.format_exc()}\n")

try:
    from api_manager import APIManager
    api = APIManager()
except Exception as e:
    log_crash(e)
    sys.exit(1)

CONFIG_FILE = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~'), 'AISystemManager_Config.json')

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                api.update_config(conf)
                return conf
        except Exception:
            pass
    default_conf = {
        "auth": {"user": "admin", "pass": "admin"},
        "Gemini": [], "OpenRouter": [], 
        "Proxy": {"enabled": False, "host": "127.0.0.1", "port": "1080"}
    }
    return default_conf

def save_config(conf):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(conf, f)
        api.update_config(conf)
    except Exception as e:
        log_crash(e)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json or {}
        conf = load_config()
        auth_data = conf.get("auth", {"user": "admin", "pass": "admin"})
        if data.get("username") == auth_data.get("user") and data.get("password") == auth_data.get("pass"):
            session['logged_in'] = True
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "نام کاربری یا رمز عبور اشتباه است."}), 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/api/test-gemini', methods=['POST'])
def test_gemini():
    data = request.json or {}
    key = data.get('api_key', '')
    result = api.test_and_fetch_gemini_models(key)
    return jsonify(result)

@app.route('/api/chat', methods=['POST'])
def chat():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json or {}
    text = data.get('text', '')
    image = data.get('image', None)
    model_name = data.get('model', 'gemini-1.5-flash')
    api_key = data.get('api_key', '')
    manual_skills = data.get('skills', [])
    
    ai_resp, sys_resp = api.send_message(model_name, api_key, manual_skills, text, image)
    return jsonify({"ai_response": ai_resp, "sys_response": sys_resp})

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        save_config(request.json or {})
        return jsonify({"status": "success"})
    return jsonify(load_config())

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    Timer(0.5, lambda: os._exit(0)).start()
    return jsonify({"status": "shutting down"})

def open_browser(port):
    url = f"http://127.0.0.1:{port}/login"
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path, f"--app={url}"])
                return
            except Exception:
                pass
    webbrowser.open(url)

if __name__ == '__main__':
    try:
        load_config()
        PORT = 65748
        Timer(1.2, open_browser, [PORT]).start()
        app.run(host='127.0.0.1', port=PORT, debug=False)
    except Exception as e:
        log_crash(e)
