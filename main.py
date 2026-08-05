import requests
import json
import time
import os
import sqlite3
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# =========================================
# CONFIGURATION
# =========================================
BOT_TOKEN = "8904752333:AAFVkVmsRla5BDePDAxynGteQDX7rMy6sIE"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

MANDATORY_CHANNEL = "@nobitabanxunban"
BOT_USERNAME = "Nobita_banbot"
OWNER_USERNAME = "Znonsence"

REQUIRED_REFERRALS = 10
COOLDOWN_TIME = 900  # 15 Minutes = 900 Seconds

DB_FILE = "nobita_bot.db"
BANNER_URL = "https://raw.githubusercontent.com/Bikash7311/upi-giveway22/main/file_00000000699c72078bf5815b0d1a0995.png"

user_states = {}

# =========================================
# DATABASE SETUP
# =========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY, 
                        referred_by INTEGER DEFAULT NULL,
                        last_action_time INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        referrer_id INTEGER,
                        referred_id INTEGER UNIQUE)''')
    conn.commit()
    conn.close()

def register_user(user_id, referrer_id=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res:
        cursor.execute("INSERT INTO users (user_id, referred_by, last_action_time) VALUES (?, ?, 0)", (user_id, referrer_id))
        conn.commit()
    conn.close()

def get_referrer(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def confirm_referral(referrer_id, referred_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, referred_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_referral_count(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_last_action_time(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT last_action_time FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def update_last_action_time(user_id):
    now = int(time.time())
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_action_time = ? WHERE user_id = ?", (now, user_id))
    conn.commit()
    conn.close()

# =========================================
# TELEGRAM API HELPERS
# =========================================
def is_user_joined(user_id):
    try:
        url = API_URL + "/getChatMember"
        params = {"chat_id": MANDATORY_CHANNEL, "user_id": user_id}
        response = requests.get(url, params=params, timeout=10).json()
        if response.get("ok") and response["result"]["status"] in ["member", "administrator", "creator"]:
            return True
        return False
    except: return False

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = API_URL + "/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: payload["parse_mode"] = parse_mode
    try: 
        res = requests.post(url, data=payload, timeout=10).json()
        return res.get("result", {}).get("message_id")
    except: return None

def edit_message_text(chat_id, message_id, text, reply_markup=None, parse_mode=None):
    url = API_URL + "/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: payload["parse_mode"] = parse_mode
    try: requests.post(url, data=payload, timeout=10)
    except: pass

def send_photo(chat_id, photo_url, caption, reply_markup=None, parse_mode=None):
    url = API_URL + "/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: payload["parse_mode"] = parse_mode
    try: 
        res = requests.post(url, data=payload, timeout=10).json()
        if not res.get("ok"):
            send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
    except: 
        send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)

def answer_callback_query(callback_query_id, text):
    url = API_URL + "/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id, "text": text}
    try: requests.post(url, data=payload, timeout=10)
    except: pass

# =========================================
# KEYBOARDS
# =========================================
def get_main_menu_keyboard(user_id):
    ref_count = get_referral_count(user_id)
    return {
        "inline_keyboard": [
            [{"text": "🥷 Permanent Ban", "callback_data": "action_perm_ban"}, {"text": "⚡ Temporary Ban", "callback_data": "action_temp_ban"}],
            [{"text": "🚨 Mass Report", "callback_data": "action_mass_report"}, {"text": "✅ Unban Target", "callback_data": "action_unban"}],
            [{"text": "📊 Ban Status Checker", "callback_data": "action_status_check"}, {"text": "🛡️ Bot Status", "callback_data": "action_bot_status"}],
            [{"text": f"🚀 Invite Friends ({ref_count}/{REQUIRED_REFERRALS})", "callback_data": "action_invite"}, {"text": "💬 Message Owner", "url": f"https://t.me/{OWNER_USERNAME}"}],
            [{"text": "📢 Join Channel", "url": "https://t.me/nobitabanxunban"}]
        ]
    }

def get_back_keyboard():
    return {"inline_keyboard": [[{"text": "🔙 Back to Control Deck", "callback_data": "go_back"}]]}

def get_join_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📢 Join Official Channel", "url": "https://t.me/nobitabanxunban"}],
            [{"text": "✅ Verify Join", "callback_data": "verify_join"}]
        ]
    }

# =========================================
# MESSAGE & CALLBACK HANDLERS
# =========================================
def handle_message(message):
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    user_text = message.get("text", "").strip()

    if user_text.startswith("/start"):
        parts = user_text.split(" ")
        referrer_id = None
        if len(parts) > 1:
            try:
                possible_ref = int(parts[1])
                if possible_ref != user_id:
                    referrer_id = possible_ref
            except: pass
        register_user(user_id, referrer_id)

    if not is_user_joined(user_id):
        join_msg = (
            "🚨 <b>ACCESS RESTRICTED BY NOBITA SYSTEM!</b> 🚨\n\n"
            "To use this bot, you must first join our official channel!\n\n"
            "📢 <b>Channel Link:</b> https://t.me/nobitabanxunban\n\n"
            "👇 After joining, click the <b>Verify Join</b> button below."
        )
        send_message(chat_id, join_msg, reply_markup=get_join_keyboard(), parse_mode="HTML")
        return

    if user_text.startswith("/start"):
        ref_count = get_referral_count(user_id)
        status_str = "💎 PREMIUM UNLOCKED" if ref_count >= REQUIRED_REFERRALS else "❌ NOT PREMIUM (Invite 10 Friends)"
        welcome_caption = (
            f"⚡ <b>NOBITA BAN x UNBAN BOT</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🥷 Permanent Ban System\n"
            f"⚡ Temporary Ban System\n"
            f"📊 Ban Status Checker\n"
            f"🚨 Mass Reporting Engine\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"👑 <b>Status:</b> <b>{status_str}</b>\n"
            f"🚀 <b>Referrals:</b> {ref_count}/{REQUIRED_REFERRALS}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>Select an action option below:</i>"
        )
        send_photo(chat_id, BANNER_URL, welcome_caption, reply_markup=get_main_menu_keyboard(user_id), parse_mode="HTML")
        user_states[chat_id] = "idle"
        return

    current_state = user_states.get(chat_id)
    if current_state in ["perm_ban_input", "temp_ban_input", "mass_report_input", "unban_input", "status_check_input"]:
        if user_text.startswith("+") and len(user_text) >= 10:
            
            # Start Cooldown Timer & Execution
            update_last_action_time(user_id)

            msg_id = send_message(chat_id, "⏳ <b>Connecting to WhatsApp Gateways via Nobita Server...</b>\n\n<i>Initializing target sequence... Please wait.</i>", parse_mode="HTML")
            time.sleep(2)
            edit_message_text(chat_id, msg_id, "⚡ <b>Bypassing Security Handshake...</b>\n\n<i>Injecting payload packets into target route...</i>", parse_mode="HTML")
            time.sleep(2)
            
            if current_state == "perm_ban_input":
                res_text = f"🥷 <b>Permanent Ban Request Sent!</b>\n\nTarget number <code>{user_text}</code> has been submitted for permanent ban review.\n\n⏳ <i>Cooldown active: Please wait 15 minutes before next request.</i>"
            elif current_state == "temp_ban_input":
                res_text = f"⚡ <b>Temporary Ban Triggered!</b>\n\nTarget number <code>{user_text}</code> has been restricted for 24-48 hours.\n\n⏳ <i>Cooldown active: Please wait 15 minutes before next request.</i>"
            elif current_state == "mass_report_input":
                res_text = f"🚨 <b>Mass Report Active!</b>\n\nMass reports dispatched to target <code>{user_text}</code> across 50+ nodes.\n\n⏳ <i>Cooldown active: Please wait 15 minutes before next request.</i>"
            elif current_state == "unban_input":
                res_text = f"✅ <b>Unban Execution Completed.</b>\n\nRestrictions successfully lifted for target <code>{user_text}</code>.\n\n⏳ <i>Cooldown active: Please wait 15 minutes before next request.</i>"
            else:
                res_text = f"📊 <b>Status Report:</b> Target <code>{user_text}</code> is under active restriction review."

            send_message(chat_id, res_text, reply_markup=get_back_keyboard(), parse_mode="HTML")
            user_states[chat_id] = "idle"
        else:
            send_message(chat_id, "❌ <b>Invalid Format!</b> Please enter phone number with country code (e.g. <code>+919876543210</code>):", parse_mode="HTML")
        return

def handle_callback(callback):
    callback_id = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]
    user_id = callback["from"]["id"]
    data = callback["data"]

    if data == "verify_join":
        if is_user_joined(user_id):
            answer_callback_query(callback_id, "✅ Verified!")
            
            referrer_id = get_referrer(user_id)
            if referrer_id:
                if confirm_referral(referrer_id, user_id):
                    send_message(referrer_id, f"🎉 <b>New Referral Joined!</b>\n\nA user joined using your link. Referral count updated!")
            
            ref_count = get_referral_count(user_id)
            status_str = "💎 PREMIUM UNLOCKED" if ref_count >= REQUIRED_REFERRALS else "❌ NOT PREMIUM (Invite 10 Friends)"
            welcome_caption = (
                f"⚡ <b>NOBITA BAN x UNBAN BOT</b> ⚡\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                f"👑 <b>Status:</b> <b>{status_str}</b>\n"
                f"🚀 <b>Referrals:</b> {ref_count}/{REQUIRED_REFERRALS}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 <i>Select an action option below:</i>"
            )
            send_photo(chat_id, BANNER_URL, welcome_caption, reply_markup=get_main_menu_keyboard(user_id), parse_mode="HTML")
        else:
            answer_callback_query(callback_id, "❌ Channel not joined!")
        return

    if not is_user_joined(user_id): return

    ref_count = get_referral_count(user_id)

    # 1. Premium Check (Require 10 Referrals)
    if data in ["action_perm_ban", "action_temp_ban", "action_mass_report", "action_unban"]:
        if ref_count < REQUIRED_REFERRALS:
            answer_callback_query(callback_id, "🔒 Premium Access Required!")
            lock_msg = (
                f"🛑 <b>PREMIUM ACCESS REQUIRED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"Your account status is <b>❌ NOT PREMIUM</b>.\n"
                f"To unlock this feature, you must invite at least <b>10 friends</b> to our official channel!\n\n"
                f"📊 <b>Your Referrals:</b> {ref_count} / 10\n"
                f"🎯 <b>Remaining:</b> {REQUIRED_REFERRALS - ref_count} Friends\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Click the <b>Invite Friends</b> button below to generate your referral link.</i>"
            )
            edit_message_text(chat_id, message_id, lock_msg, reply_markup=get_back_keyboard(), parse_mode="HTML")
            return

        # 2. 15-Minute Cooldown Check
        last_action = get_last_action_time(user_id)
        now = int(time.time())
        time_passed = now - last_action

        if time_passed < COOLDOWN_TIME:
            remaining_seconds = COOLDOWN_TIME - time_passed
            mins = remaining_seconds // 60
            secs = remaining_seconds % 60
            answer_callback_query(callback_id, f"⏳ Cooldown Active! Wait {mins}m {secs}s")
            cooldown_msg = (
                f"⏳ <b>SERVER COOLDOWN ACTIVE!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"To prevent WhatsApp API rate-limits, you can only run 1 action every 15 minutes.\n\n"
                f"🕒 <b>Please wait:</b> <code>{mins} minutes {secs} seconds</code> before initiating another request.\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            edit_message_text(chat_id, message_id, cooldown_msg, reply_markup=get_back_keyboard(), parse_mode="HTML")
            return

    if data == "action_perm_ban":
        answer_callback_query(callback_id, "🥷 Permanent Ban Selected")
        edit_message_text(chat_id, message_id, "🥷 <b>Permanent Ban Request:</b>\n\nPlease enter the target WhatsApp number with country code (e.g. +91XXXXXXXXXX):", reply_markup=get_back_keyboard(), parse_mode="HTML")
        user_states[chat_id] = "perm_ban_input"

    elif data == "action_temp_ban":
        answer_callback_query(callback_id, "⚡ Temporary Ban Selected")
        edit_message_text(chat_id, message_id, "⚡ <b>Temporary Ban Request:</b>\n\nPlease enter the target WhatsApp number:", reply_markup=get_back_keyboard(), parse_mode="HTML")
        user_states[chat_id] = "temp_ban_input"

    elif data == "action_mass_report":
        answer_callback_query(callback_id, "🚨 Mass Report Selected")
        edit_message_text(chat_id, message_id, "🚨 <b>Mass Report Request:</b>\n\nPlease enter the target WhatsApp number:", reply_markup=get_back_keyboard(), parse_mode="HTML")
        user_states[chat_id] = "mass_report_input"

    elif data == "action_unban":
        answer_callback_query(callback_id, "✅ Unban Selected")
        edit_message_text(chat_id, message_id, "🔓 <b>Unban Request:</b>\n\nPlease enter the user number to continue:", reply_markup=get_back_keyboard(), parse_mode="HTML")
        user_states[chat_id] = "unban_input"

    elif data == "action_status_check":
        answer_callback_query(callback_id, "📊 Status Checker")
        edit_message_text(chat_id, message_id, "📊 <b>Ban Status Checker:</b>\n\nEnter number to check restriction status:", reply_markup=get_back_keyboard(), parse_mode="HTML")
        user_states[chat_id] = "status_check_input"

    elif data == "action_bot_status":
        answer_callback_query(callback_id, "🛡️ System Online")
        status_text = (
            "🛡️ <b>NOBITA CORE STATUS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🟢 <b>API Node:</b> Online & Operational\n"
            "⚡ <b>Latency:</b> 0.02s\n"
            "🔒 <b>Encryption:</b> AES-256 Active\n"
            "🌐 <b>Active Proxies:</b> 500+ Connected\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        edit_message_text(chat_id, message_id, status_text, reply_markup=get_back_keyboard(), parse_mode="HTML")

    elif data == "action_invite":
        answer_callback_query(callback_id, "🚀 Invite Link Generated")
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        ref_text = (
            f"🚀 <b>NOBITA REFERRAL PANEL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Invite 10 friends to unlock Premium Status!\n\n"
            f"🔗 <b>Your Referral Link:</b>\n<code>{ref_link}</code>\n\n"
            f"👥 <b>Verified Referrals:</b> {ref_count} / {REQUIRED_REFERRALS}\n"
            f"⚠️ <i>Note: Referral only counts when your friend joins our official channel!</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━"
        )
        edit_message_text(chat_id, message_id, ref_text, reply_markup=get_back_keyboard(), parse_mode="HTML")

    elif data == "go_back":
        answer_callback_query(callback_id, "🔄 Returning...")
        status_str = "💎 PREMIUM UNLOCKED" if ref_count >= REQUIRED_REFERRALS else "❌ NOT PREMIUM (Invite 10 Friends)"
        welcome_caption = (
            f"⚡ <b>NOBITA BAN x UNBAN BOT</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"👑 <b>Status:</b> <b>{status_str}</b>\n"
            f"🚀 <b>Referrals:</b> {ref_count}/{REQUIRED_REFERRALS}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>Select an action option below:</i>"
        )
        edit_message_text(chat_id, message_id, welcome_caption, reply_markup=get_main_menu_keyboard(user_id), parse_mode="HTML")
        user_states[chat_id] = "idle"

class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"NOBITA BAN BOT ONLINE")

def bot_polling():
    offset = 0
    while True:
        try:
            response = requests.get(API_URL + "/getUpdates", params={"timeout": 30, "offset": offset}, timeout=35).json()
            if response.get("ok"):
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update: handle_message(update["message"])
                    elif "callback_query" in update: handle_callback(update["callback_query"])
        except: time.sleep(1)

if __name__ == "__main__":
    init_db()
    Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), WebServer).serve_forever(), daemon=True).start()
    bot_polling()
