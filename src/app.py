import os
import sys
import json
import logging
import traceback
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

log_file_path = os.path.join(base_dir, "app_debug.log")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file_path, mode='a', encoding='utf-8'), logging.StreamHandler(sys.stdout)])

internal_templates = os.path.join(base_dir, '_internal', 'templates')
root_templates = os.path.join(base_dir, 'templates')
template_folder = internal_templates if os.path.exists(internal_templates) else (root_templates if os.path.exists(root_templates) else os.path.join(base_dir, 'templates'))

app = Flask(__name__, template_folder=template_folder)
app.secret_key = "enterprise_infrastructure_secret_key"

try:
    from api_manager import APIManager
    api = APIManager()
except Exception as e:
    logging.critical(f"Failed to initialize APIManager: {str(e)}")
    sys.exit(1)

CONFIG_FILE = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~'), 'AISystemManager_Config.json')

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                # آپگرید کانفیگ قدیمی به سیستم چندکاربره
                if "users" not in conf:
                    old_pass = conf.get("auth", {}).get("pass", "admin")
                    conf["users"] = {
                        "admin": {"password": old_pass, "role": "admin"},
                        "user1": {"password": "123", "role": "user"},
                        "user2": {"password": "123", "role": "user"}
                    }
                api.update_config(conf)
                return conf
        except Exception as e:
            logging.warning(f"Error reading config: {e}")
            
    default_conf = {
        "users": {
            "admin": {"password": "admin", "role": "admin"},
            "user1": {"password": "123", "role": "user"},
            "user2": {"password": "123", "role": "user"}
        },
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
        logging.error(f"Failed to save configuration: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")
        conf = load_config()
        
        users = conf.get("users", {})
        if username in users and users[username]["password"] == password:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = users[username]["role"]
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "نام کاربری یا رمز عبور اشتباه است."}), 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'), role=session.get('role'))

@app.route('/api/test-gemini', methods=['POST'])
def test_gemini():
    if session.get('role') != 'admin': return jsonify({"status": "error", "message": "عدم دسترسی"})
    data = request.json or {}
    return jsonify(api.test_and_fetch_gemini_models(data.get('api_key', '')))

@app.route('/api/chat', methods=['POST'])
def chat():
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json or {}
    text = data.get('text', '')
    image = data.get('image', None)
    model_name = data.get('model', 'gemini-1.5-flash')
    api_key = data.get('api_key', '')
    manual_skills = data.get('skills', []) if session.get('role') == 'admin' else [] # محدودیت اسکیل برای کاربر عادی
    
    ai_resp, sys_resp = api.send_message(model_name, api_key, manual_skills, text, image)
    return jsonify({"ai_response": ai_resp, "sys_response": sys_resp})

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 403
    if request.method == 'POST':
        save_config(request.json or {})
        return jsonify({"status": "success"})
    return jsonify(load_config())

@app.route('/api/restart', methods=['POST'])
def restart():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 403
    logging.info("Restarting server...")
    def do_restart():
        os.execl(sys.executable, sys.executable, *sys.argv)
    Timer(0.5, do_restart).start()
    return jsonify({"status": "restarting"})

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 403
    logging.info("Shutting down...")
    Timer(0.5, lambda: os._exit(0)).start()
    return jsonify({"status": "shutting down"})

def open_browser(port):
    url = f"http://127.0.0.1:{port}/login"
    try: webbrowser.open_new_tab(url)
    except: pass

if __name__ == '__main__':
    try:
        load_config()
        PORT = 8585
        Timer(1.2, open_browser, [PORT]).start()
        app.run(host='127.0.0.1', port=PORT, debug=False)
    except Exception as e:
        logging.critical(traceback.format_exc())
