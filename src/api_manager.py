import os
import json
import requests
import re
from system_controller import SystemController

class APIManager:
    def __init__(self):
        self.config = {
            "auth": {"user": "admin", "pass": "admin"},
            "Gemini": [], 
            "OpenRouter": [], 
            "Proxy": {"enabled": False, "host": "127.0.0.1", "port": "1080"}
        }
        self.sys_controller = SystemController()
        
        # بانک جامع مهارت‌های تخصصی زیرساخت و شبکه
        self.skills_bank = {
            "mikrotik_firewall": "دانش میکروتیک و RouterOS: نگارش اسکریپت‌های فایروال، رول‌های NAT، مانیتورینگ پورت‌ها و مدیریت ترافیک.",
            "ubuntu_tunneling": "دانش اوبونتو و تانلینگ: راه‌اندازی انواع تانل‌ها (GRE، WireGuard، Xray، V2Ray، IPIP) و بهینه‌سازی مسیرها.",
            "active_directory": "دانش مایکروسافت و اکتیو دایرکتوری: مدیریت Domain Controller، پالیسی‌ها (GPO)، مدیریت کاربران و سرویس‌های ویندوزی.",
            "virtualization_esxi": "دانش مجازی‌سازی و ESXi: مدیریت ماشین‌های مجازی، پایش منابع، تنظیمات vSwitch و ذخیره‌سازها.",
            "docker_automation": "دانش دواپس و اتوماسیون: نگارش فایل‌های Docker Compose، اتوماسیون سرویس‌ها و مدیریت کانتینرها.",
            "windows_admin": "دانش پیشرفته ویندوز: مدیریت سرویس‌ها، رجیستری، اسکریپت‌نویسی PowerShell و بررسی لاگ‌های امنیتی."
        }

    def update_config(self, config_dict):
        self.config.update(config_dict)

    def get_proxies(self):
        proxy_conf = self.config.get("Proxy", {})
        if proxy_conf.get("enabled"):
            auth = ""
            user = proxy_conf.get("username", "")
            pwd = proxy_conf.get("password", "")
            if user and pwd: auth = f"{user}:{pwd}@"
            host = proxy_conf.get("host", "127.0.0.1")
            port = proxy_conf.get("port", "1080")
            proxy_url = f"socks5://{auth}{host}:{port}"
            return {"http": proxy_url, "https": proxy_url}
        return None

    def test_and_fetch_gemini_models(self, api_key):
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            response = requests.get(url, proxies=self.get_proxies(), timeout=15)
            if response.status_code == 200:
                models = response.json().get("models", [])
                valid_models = [m["name"].replace("models/", "") for m in models if "generateContent" in m.get("supportedGenerationMethods", [])]
                return {"status": "success", "models": valid_models}
            else:
                return {"status": "error", "message": f"خطا در اعتبارسنجی کلید ({response.status_code}): {response.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def process_system_commands(self, text: str) -> tuple[str, str]:
        sys_outputs = []
        clean_text = text
        commands = re.findall(r'\[SYS_CMD:(.*?):(.*?)\]', text)
        for cmd_type, args in commands:
            result = self.sys_controller.execute_command(cmd_type, args)
            sys_outputs.append(result)
            clean_text = clean_text.replace(f"[SYS_CMD:{cmd_type}:{args}]", "")
        return clean_text.strip(), "\n".join(sys_outputs)

    def send_message(self, model_name, api_key, manual_skills, text, image_base64=None) -> tuple[str, str]:
        skills_context = "\nمهارت‌های فعال سیستم برای استفاده:\n"
        if manual_skills and len(manual_skills) > 0:
            for s in manual_skills:
                if s in self.skills_bank:
                    skills_context += f"- {self.skills_bank[s]}\n"
        else:
            skills_context += "- دستیار هوشمند با دسترسی به تحلیل سیستم‌عامل و شبکه.\n"

        base_cmd = " برای کارهای سیستمی فقط با این فرمت پاسخ دهید: [SYS_CMD:POWERSHELL:دستور] یا [SYS_CMD:TYPE:متن] یا [SYS_CMD:PRESS:enter] یا [SYS_CMD:CLICK:]"
        sys_inst = "شما یک مهندس ارشد و ادمین زیرساخت فناوری هستید." + skills_context + base_cmd
        proxies = self.get_proxies()

        if "gemini" in model_name.lower():
            if not api_key: return "خطا: کلید API جمینای وارد نشده است.", ""
            
            parts = []
            if text: parts.append({"text": text})
            if image_base64:
                mime_type = image_base64.split(";")[0].split(":")[1]
                img_data = image_base64.split(",")[1]
                parts.append({"inline_data": {"mime_type": mime_type, "data": img_data}})

            data = {
                "systemInstruction": {"parts": [{"text": sys_inst}]},
                "contents": [{"parts": parts}]
            }

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                response = requests.post(url, headers={'Content-Type': 'application/json'}, json=data, proxies=proxies, timeout=30)
                if response.status_code == 200:
                    ai_text = response.json()['candidates'][0]['content']['parts'][0]['text']
                    return self.process_system_commands(ai_text)
                else:
                    return f"خطای سرور گوگل ({response.status_code}): {response.text}", ""
            except Exception as e:
                return f"خطای ارتباطی با جمینای: {str(e)}", ""
        else:
            keys = self.config.get("OpenRouter", [])
            if not keys: return "خطا: کلید OpenRouter تنظیم نشده است.", ""
            
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {keys[0]}", "Content-Type": "application/json"}
            data = {
                "model": model_name if "/" in model_name else "deepseek/deepseek-chat",
                "messages": [
                    {"role": "system", "content": sys_inst},
                    {"role": "user", "content": text}
                ]
            }
            try:
                response = requests.post(url, headers=headers, json=data, proxies=proxies, timeout=30)
                if response.status_code == 200:
                    ai_text = response.json()["choices"][0]["message"]["content"]
                    return self.process_system_commands(ai_text)
                else:
                    return f"خطای OpenRouter: {response.text}", ""
            except Exception as e:
                return f"خطای ارتباطی: {str(e)}", ""
