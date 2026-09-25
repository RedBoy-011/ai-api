import os
import sys
import json
import logging
import traceback
import subprocess
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# تنظیم مسیر پایه و فایل لاگ
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

log_file_path = os.path.join(base_dir, "app_debug.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logging.info("=== STEP 1: Initializing Application Environment ===")
logging.info(f"Execution Base Directory: {base_dir}")

# تعیین مسیر پوشه templates
internal_templates = os.path.join(base_dir, '_internal', 'templates')
root_templates = os.path.join(base_dir, 'templates')

if os.path.exists(internal_templates):
    template_folder = internal_templates
    logging.info(f"Templates resolved to internal: {internal_templates}")
elif os.path.exists(root_templates):
    template_folder = root_templates
    logging.info(f"Templates resolved to root: {root_templates}")
else:
    template_folder = os.path.join(base_dir, 'templates')
    logging.warning(f"Templates directory not explicitly matched. Fallback to: {template_folder}")

logging.info("=== STEP 2: Creating Flask App Instance ===")
app = Flask(__name__, template_folder=template_folder)
app.secret_key = "infrastructure_secret_key_secure_session"

logging.info("=== STEP 3: Initializing APIManager and Skills Bank ===")
try:
    from api_manager import APIManager
    api = APIManager()
    logging.info("APIManager initialized successfully.")
except Exception as e:
    logging.error(f"Failed to initialize APIManager: {str(e)}")
    logging.error(traceback.format_exc())
    sys.exit(1)

CONFIG_FILE = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~'), 'AISystemManager_Config.json')
logging.info(f"Configuration file target path: {CONFIG_FILE}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                api.update_config(conf)
                logging.info("Configuration loaded from file successfully.")
                return conf
        except Exception as e:
            logging.warning(f"Error reading configuration file: {e}")
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
        logging.info("Configuration updated and saved to disk.")
    except Exception as e:
        logging.error(f"Failed to save configuration: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json or {}
        conf = load_config()
        auth_data = conf.get("auth", {"user": "admin", "pass": "admin"})
        if data.get("username") == auth_data.get("user") and data.get("password") == auth_data.get("pass"):
            session['logged_in'] = True
            logging.info("User login successful.")
            return jsonify({"status": "success"})
        logging.warning("User login failed: invalid credentials.")
        return jsonify({"status": "error", "message": "Invalid username or password"}), 401
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
    logging.info("Testing Gemini API key connection...")
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
    
    logging.info(f"Processing chat request for model '{model_name}' with skills: {manual_skills}")
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
    logging.info("Shutdown request received. Terminating process...")
    Timer(0.5, lambda: os._exit(0)).start()
    return jsonify({"status": "shutting down"})

def open_browser(port):
    url = f"http://127.0.0.1:{port}/login"
    logging.info(f"Attempting to launch browser at: {url}")
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path, f"--app={url}"])
                logging.info(f"Chrome App Window opened via: {path}")
                return
            except Exception as e:
                logging.warning(f"Could not open Chrome App window: {e}")
    webbrowser.open(url)
    logging.info("Default system browser invoked.")

if __name__ == '__main__':
    try:
        load_config()
        PORT = 65748
        logging.info(f"=== STEP 4: Starting Local Server on 127.0.0.1:{PORT} ===")
        Timer(1.2, open_browser, [PORT]).start()
        app.run(host='127.0.0.1', port=PORT, debug=False)
    except Exception as e:
        logging.critical(f"FATAL: Application failed to start: {str(e)}")
        logging.critical(traceback.format_exc())
