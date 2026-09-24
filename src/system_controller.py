import subprocess
import pyautogui

class SystemController:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5

    def execute_command(self, cmd_type: str, args: str) -> str:
        try:
            if cmd_type == "POWERSHELL":
                # اجرای دستورات واقعی پاورشل در ویندوز
                result = subprocess.run(["powershell", "-Command", args], capture_output=True, text=True, timeout=10)
                return f"خروجی PowerShell:\n{result.stdout if result.stdout else result.stderr}"
            elif cmd_type == "TYPE":
                pyautogui.write(args, interval=0.03)
                return f"متن تایپ شد: {args}"
            elif cmd_type == "CLICK":
                pyautogui.click()
                return "کلیک چپ انجام شد."
            elif cmd_type == "PRESS":
                pyautogui.press(args.lower())
                return f"کلید {args} فشرده شد."
            return f"دستور ناشناخته: {cmd_type}"
        except Exception as e:
            return f"خطا در اجرای دستور سیستم: {str(e)}"
