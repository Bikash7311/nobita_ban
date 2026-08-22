from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sqlite3
from threading import Thread
import time
import requests

# =========================================
# CONFIGURATION
# =========================================
BOT_TOKEN = "8904752333:AAFVkVmsRla5BDePDAxynGteQDX7rMy6sIE"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

MANDATORY_CHANNEL = "@nobitabanxunban"
BOT_USERNAME = "Nobita_banbot"
OWNER_USERNAME = "Znonsence"
OWNER_ID = 6132146801

REQUIRED_REFERRALS = 15  # Updated from 10 to 15 Referrals
COOLDOWN_TIME = 900  # 15 Minutes

DB_FILE = "nobita_bot.db"
BANNER_URL = "https://raw.githubusercontent.com/Bikash7311/upi-giveway22/main/file_00000000699c72078bf5815b0d1a0995.png"
ANIME_LOADER_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnFlcWs4d3N3enN2dWdrNm5icmdsbTZwdjJzcmJjYW9ndTllZXhmdSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/L5aXbsMT2N7b2/giphy.gif"

user_states = {}


# =========================================
# DATABASE SETUP
# =========================================
def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY, 
                        referred_by INTEGER DEFAULT NULL,
                        last_action_time INTEGER DEFAULT 0)""")
  cursor.execute("""CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        referrer_id INTEGER,
                        referred_id INTEGER UNIQUE)""")
  cursor.execute("""CREATE TABLE IF NOT EXISTS manual_premium (
                        user_id INTEGER PRIMARY KEY)""")
  conn.commit()
  conn.close()


def register_user(user_id, referrer_id=None):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
  res = cursor.fetchone()
  if not res:
    cursor.execute(
        "INSERT INTO users (user_id, referred_by, last_action_time) VALUES"
        " (?, ?, 0)",
        (user_id, referrer_id),
    )
    conn.commit()
  conn.close()


def get_all_users():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("SELECT user_id FROM users")
  users = cursor.fetchall()
  conn.close()
  return [u[0] for u in users]


def get_referrer(user_id):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT referred_by FROM users WHERE user_id = ?", (user_id,)
  )
  res = cursor.fetchone()
  conn.close()
  return res[0] if res else None


def confirm_referral(referrer_id, referred_id):
  try:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
        (referrer_id, referred_id),
    )
    conn.commit()
    conn.close()
    return True
  except sqlite3.IntegrityError:
    conn.close()
    return False


def get_referral_count(user_id):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)
  )
  count = cursor.fetchone()[0]
  conn.close()
  return count


def get_last_action_time(user_id):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT last_action_time FROM users WHERE user_id = ?", (user_id,)
  )
  res = cursor.fetchone()
  conn.close()
  return res[0] if res else 0


def update_last_action_time(user_id):
  now = int(time.time())
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET last_action_time = ? WHERE user_id = ?", (now, user_id)
  )
  conn.commit()
  conn.close()


def add_manual_premium(user_id):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR IGNORE INTO manual_premium (user_id) VALUES (?)", (user_id,)
  )
  conn.commit()
  conn.close()


def remove_manual_premium(user_id):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("DELETE FROM manual_premium WHERE user_id = ?", (user_id,))
  conn.commit()
  conn.close()


def is_manual_premium(user_id):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT user_id FROM manual_premium WHERE user_id = ?", (user_id,)
  )
  res = cursor.fetchone()
  conn.close()
  return res is not None


def get_all_manual_premium():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("SELECT user_id FROM manual_premium")
  users = cursor.fetchall()
  conn.close()
  return [u[0] for u in users]


def has_premium_access(user_id):
  if user_id == OWNER_ID:
    return True
  if is_manual_premium(user_id):
    return True
  if get_referral_count(user_id) >= REQUIRED_REFERRALS:
    return True
  return False


# =========================================
# TELEGRAM API HELPERS
# =========================================
def is_user_joined(user_id):
  try:
    url = API_URL + "/getChatMember"
    params = {"chat_id": MANDATORY_CHANNEL, "user_id": user_id}
    response = requests.get(url, params=params, timeout=10).json()
    if response.get("ok") and response["result"]["status"] in [
        "member",
        "administrator",
        "creator",
    ]:
      return True
    return False
  except:
    return False


def send_message(chat_id, text, reply_markup=None, parse_mode=None):
  url = API_URL + "/sendMessage"
  payload = {"chat_id": chat_id, "text": text}
  if reply_markup:
    payload["reply_markup"] = json.dumps(reply_markup)
  if parse_mode:
    payload["parse_mode"] = parse_mode
  try:
    res = requests.post(url, data=payload, timeout=10).json()
    return res.get("result", {}).get("message_id")
  except:
    return None


def edit_message_text(
    chat_id, message_id, text, reply_markup=None, parse_mode=None
):
  url = API_URL + "/editMessageText"
  payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
  if reply_markup:
    payload["reply_markup"] = json.dumps(reply_markup)
  if parse_mode:
    payload["parse_mode"] = parse_mode
  try:
    requests.post(url, data=payload, timeout=10)
  except:
    pass


def send_photo(chat_id, photo_url, caption, reply_markup=None, parse_mode=None):
  url = API_URL + "/sendPhoto"
  payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption}
  if reply_markup:
    payload["reply_markup"] = json.dumps(reply_markup)
  if parse_mode:
    payload["parse_mode"] = parse_mode
  try:
    res = requests.post(url, data=payload, timeout=10).json()
    if not res.get("ok"):
      send_message(
          chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode
      )
  except:
    send_message(
        chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode
    )


def send_animation(
    chat_id, animation_url, caption, reply_markup=None, parse_mode=None
):
  url = API_URL + "/sendAnimation"
  payload = {"chat_id": chat_id, "animation": animation_url, "caption": caption}
  if reply_markup:
    payload["reply_markup"] = json.dumps(reply_markup)
  if parse_mode:
    payload["parse_mode"] = parse_mode
  try:
    res = requests.post(url, data=payload, timeout=10).json()
    if res.get("ok"):
      return res.get("result", {}).get("message_id")
    else:
      return send_message(
          chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode
      )
  except:
    return send_message(
        chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode
    )


def edit_message_caption(
    chat_id, message_id, caption, reply_markup=None, parse_mode=None
):
  url = API_URL + "/editMessageCaption"
  payload = {"chat_id": chat_id, "message_id": message_id, "caption": caption}
  if reply_markup:
    payload["reply_markup"] = json.dumps(reply_markup)
  if parse_mode:
    payload["parse_mode"] = parse_mode
  try:
    requests.post(url, data=payload, timeout=10)
  except:
    pass


def answer_callback_query(callback_query_id, text, show_alert=False):
  url = API_URL + "/answerCallbackQuery"
  payload = {
      "callback_query_id": callback_query_id,
      "text": text,
      "show_alert": show_alert,
  }
  try:
    requests.post(url, data=payload, timeout=10)
  except:
    pass


# =========================================
# KEYBOARDS
# =========================================
def get_main_menu_keyboard(user_id):
  ref_count = get_referral_count(user_id)
  return {
      "inline_keyboard": [
          [
              {"text": "💥 Permanent Ban", "callback_data": "action_perm_ban"},
              {"text": "⏳ Temporary Ban", "callback_data": "action_temp_ban"},
          ],
          [
              {
                  "text": f"💬 Contact Owner: {OWNER_USERNAME}",
                  "url": f"https://t.me/{OWNER_USERNAME}",
              }
          ],
          [
              {"text": "🚨 Mass Report", "callback_data": "action_mass_report"},
              {"text": "🔓 Unban Target", "callback_data": "action_unban"},
          ],
          [
              {
                  "text": "💎 GET PREMIUM",
                  "callback_data": "action_get_premium",
              },
              {"text": "⚙️ System Status", "callback_data": "action_bot_status"},
          ],
          [
              {
                  "text": (
                      f"🎁 Invite Earn ({ref_count}/{REQUIRED_REFERRALS})"
                  ),
                  "callback_data": "action_invite",
              }
          ],
          [{
              "text": "🌐 Official Channel",
              "url": "https://t.me/nobitabanxunban",
          }],
      ]
  }


def get_back_keyboard():
  return {
      "inline_keyboard": [
          [
              {
                  "text": f"💬 DM Owner: {OWNER_USERNAME}",
                  "url": f"https://t.me/{OWNER_USERNAME}",
              }
          ],
          [{"text": "⬅️ Back to Menu", "callback_data": "go_back"}],
      ]
  }


def get_buy_premium_keyboard():
  return {
      "inline_keyboard": [
          [
              {
                  "text": f"💬 DM Owner: {OWNER_USERNAME}",
                  "url": f"https://t.me/{OWNER_USERNAME}",
              }
          ],
          [{"text": "⬅️ Back to Menu", "callback_data": "go_back"}],
      ]
  }


def get_join_keyboard():
  return {
      "inline_keyboard": [
          [{
              "text": "📢 Join Official Channel",
              "url": "https://t.me/nobitabanxunban",
          }],
          [{"text": "✅ Verify Membership", "callback_data": "verify_join"}],
      ]
  }


# =========================================
# 10-SECOND ACTION LOADER ENGINE
# =========================================
def run_10s_anime_animation(chat_id, action_title, target_number):
  init_caption = (
      f"⚡ <b>[ CORE ENGINE ACTIVATING ]</b> ⚡\n"
      f"🎯 <b>Action:</b> <code>{action_title}</code>\n"
      f"📞 <b>Target:</b> <code>{target_number}</code>\n\n"
      f"⏳ <code>[▒▒▒▒▒▒▒▒▒▒] 0%</code> — Initializing Gateway..."
  )

  msg_id = send_animation(
      chat_id, ANIME_LOADER_URL, init_caption, parse_mode="HTML"
  )

  stages = [
      (25, "███▒▒▒▒▒▒▒", "Overriding Node Defenses..."),
      (50, "█████▒▒▒▒▒", "Deploying Heavy Payload..."),
      (80, "████████▒▒", "Executing Network Strike..."),
      (100, "██████████", "Target Operations Complete!"),
  ]

  for percent, bar, status in stages:
    time.sleep(2.5)
    updated_caption = (
        f"⚡ <b>[ CORE ENGINE ACTIVATING ]</b> ⚡\n"
        f"🎯 <b>Action:</b> <code>{action_title}</code>\n"
        f"📞 <b>Target:</b> <code>{target_number}</code>\n\n"
        f"⏳ <code>[{bar}] {percent}%</code> — {status}"
    )
    edit_message_caption(chat_id, msg_id, updated_caption, parse_mode="HTML")


# =========================================
# MESSAGE & CALLBACK HANDLERS
# =========================================
def handle_message(message):
  chat_id = message["chat"]["id"]
  user_id = message["from"]["id"]
  user_text = message.get("text", "").strip()

  if user_text == "/stats" and user_id == OWNER_ID:
    all_users = get_all_users()
    manual_prems = get_all_manual_premium()
    stats_msg = (
        "📊 ─────── <b>[ DATABASE STATS ]</b> ─────── 📊\n\n"
        "┌── 📈 <b><u>SYSTEM METRICS</u></b>\n"
        f"├ 👤 <b>Total Registered Users:</b> <code>{len(all_users)}</code>\n"
        f"├ 👑 <b>Manual Premium Users:</b> <code>{len(manual_prems)}</code>\n"
        "└ 🟢 <b>Database Status:</b> Operational & Active\n\n"
        "❖ ───────────────────────────── ❖"
    )
    send_message(chat_id, stats_msg, parse_mode="HTML")
    return

  if user_text.startswith("/addpremium") and user_id == OWNER_ID:
    parts = user_text.split()
    if len(parts) > 1 and parts[1].isdigit():
      target_uid = int(parts[1])
      add_manual_premium(target_uid)
      send_message(
          chat_id,
          f"✅ <b>Success:</b> User <code>{target_uid}</code> has been given"
          " Premium Access!",
          parse_mode="HTML",
      )
    else:
      send_message(
          chat_id,
          "⚠️ <b>Usage:</b> <code>/addpremium <user_id></code>",
          parse_mode="HTML",
      )
    return

  if user_text.startswith("/removepremium") and user_id == OWNER_ID:
    parts = user_text.split()
    if len(parts) > 1 and parts[1].isdigit():
      target_uid = int(parts[1])
      remove_manual_premium(target_uid)
      send_message(
          chat_id,
          f"🚫 <b>Success:</b> Premium Access removed for user"
          f" <code>{target_uid}</code>.",
          parse_mode="HTML",
      )
    else:
      send_message(
          chat_id,
          "⚠️ <b>Usage:</b> <code>/removepremium <user_id></code>",
          parse_mode="HTML",
      )
    return

  if user_text == "/premiumlist" and user_id == OWNER_ID:
    prems = get_all_manual_premium()
    list_text = "👑 ─────── <b>[ MANUAL PREMIUM USERS ]</b> ─────── 👑\n\n"
    if prems:
      for uid in prems:
        list_text += f"• <code>{uid}</code>\n"
    else:
      list_text += "<i>No manual premium users added yet.</i>"
    send_message(chat_id, list_text, parse_mode="HTML")
    return

  if user_text.startswith("/broadcast") and user_id == OWNER_ID:
    broadcast_msg = user_text.replace("/broadcast", "").strip()
    if broadcast_msg:
      status_msg_id = send_message(
          chat_id,
          "⏳ <b>[ BROADCAST IN PROGRESS ]</b>\n\n<i>Sending network"
          " signals...</i>",
          parse_mode="HTML",
      )
      all_users = get_all_users()
      sent_count = 0
      for uid in all_users:
        try:
          send_message(uid, broadcast_msg, parse_mode="HTML")
          sent_count += 1
          time.sleep(0.05)
        except:
          continue
      edit_message_text(
          chat_id,
          status_msg_id,
          "✅ <b>[ BROADCAST COMPLETED ]</b>\n\n🎯 <b>Delivered"
          f" To:</b> <code>{sent_count}</code> users.",
          parse_mode="HTML",
      )
    else:
      send_message(
          chat_id,
          "❌ <b>Usage:</b> <code>/broadcast Your text here</code>",
          parse_mode="HTML",
      )
    return

  if user_text.startswith("/start"):
    parts = user_text.split(" ")
    referrer_id = None
    if len(parts) > 1:
      try:
        possible_ref = int(parts[1])
        if possible_ref != user_id:
          referrer_id = possible_ref
      except:
        pass
    register_user(user_id, referrer_id)

  if not is_user_joined(user_id):
    join_msg = (
        "╭───────────────────────╮\n"
        "   ⚠️ <b>ACCESS RESTRICTED</b>\n"
        "╰───────────────────────╯\n\n"
        "<blockquote>To access <b>NOBITA BAN X UNBAN PREMIUM BOT</b>"
        " features, you must join our official network channel"
        " first.</blockquote>\n\n"
        "📌 <b>Channel:</b> @nobitabanxunban\n\n"
        "👇 <i>Click the verification button below after joining!</i>"
    )
    send_message(
        chat_id, join_msg, reply_markup=get_join_keyboard(), parse_mode="HTML"
    )
    return

  if user_text.startswith("/start"):
    ref_count = get_referral_count(user_id)
    status_str = (
        "💎 PREMIUM ACCESS"
        if has_premium_access(user_id)
        else f"❌ NO PREMIUM"
    )
    welcome_caption = (
        "⚡ <b>NOBITA BAN X UNBAN PREMIUM BOT</b> ⚡\n\n"
        "Welcome! Select an option below to start:\n\n"
        f"👤 <b>Your ID:</b> <code>{user_id}</code>\n"
        f"👑 <b>Status:</b> <b>{status_str}</b>\n"
        f"🚀 <b>Referrals:</b> <code>{ref_count}/{REQUIRED_REFERRALS}</code>"
    )
    send_photo(
        chat_id,
        BANNER_URL,
        welcome_caption,
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode="HTML",
    )
    user_states[chat_id] = "idle"
    return

  current_state = user_states.get(chat_id)
  if current_state in [
      "perm_ban_input",
      "temp_ban_input",
      "mass_report_input",
      "unban_input",
  ]:
    if user_text.startswith("+") and len(user_text) >= 10:

      update_last_action_time(user_id)

      action_names = {
          "perm_ban_input": "Permanent Ban",
          "temp_ban_input": "Temporary Ban",
          "mass_report_input": "Mass Report",
          "unban_input": "Unban Execution",
      }
      action_name = action_names.get(current_state, "System Action")

      run_10s_anime_animation(chat_id, action_name, user_text)

      if current_state == "perm_ban_input":
        res_text = (
            "╭───────────────────────╮\n"
            "   💥 <b>[ PERMANENT BAN SENT ]</b>\n"
            "╰───────────────────────╯\n\n"
            f"🎯 <b>Target Number:</b> <code>{user_text}</code>\n"
            "🛡️ <b>Status:</b> Payload delivered successfully.\n\n"
            "⏳ <i>Server Cooldown: 15 minutes lock active.</i>"
        )
      elif current_state == "temp_ban_input":
        res_text = (
            "╭───────────────────────╮\n"
            "   ⏳ <b>[ TEMPORARY BAN SENT ]</b>\n"
            "╰───────────────────────╯\n\n"
            f"🎯 <b>Target Number:</b> <code>{user_text}</code>\n"
            "🛡️ <b>Status:</b> Restricted for 24-48 hours window.\n\n"
            "⏳ <i>Server Cooldown: 15 minutes lock active.</i>"
        )
      elif current_state == "mass_report_input":
        res_text = (
            "╭───────────────────────╮\n"
            "   🚨 <b>[ MASS REPORT ACTIVE ]</b>\n"
            "╰───────────────────────╯\n\n"
            f"🎯 <b>Target Number:</b> <code>{user_text}</code>\n"
            "🛡️ <b>Status:</b> Dispatched across 50+ network nodes.\n\n"
            "⏳ <i>Server Cooldown: 15 minutes lock active.</i>"
        )
      else:
        res_text = (
            "╭───────────────────────╮\n"
            "   🔓 <b>[ UNBAN EXECUTED ]</b>\n"
            "╰───────────────────────╯\n\n"
            f"🎯 <b>Target Number:</b> <code>{user_text}</code>\n"
            "🛡️ <b>Status:</b> Account restrictions cleared.\n\n"
            "⏳ <i>Server Cooldown: 15 minutes lock active.</i>"
        )

      send_message(
          chat_id,
          res_text,
          reply_markup=get_back_keyboard(),
          parse_mode="HTML",
      )
      user_states[chat_id] = "idle"
    else:
      send_message(
          chat_id,
          "⚠️ <b>[ INVALID FORMAT ]</b>\n\nPlease send the phone number with"
          " country code (e.g., <code>+919876543210</code>):",
          parse_mode="HTML",
      )
    return


def handle_callback(callback):
  callback_id = callback["id"]
  chat_id = callback["message"]["chat"]["id"]
  message_id = callback["message"]["message_id"]
  user_id = callback["from"]["id"]
  data = callback["data"]

  if data == "verify_join":
    if is_user_joined(user_id):
      answer_callback_query(callback_id, "✅ Membership Verified!")

      referrer_id = get_referrer(user_id)
      if referrer_id:
        if confirm_referral(referrer_id, user_id):
          send_message(
              referrer_id,
              "🎉 <b>[ NEW REFERRAL ]</b>\n\nA user completed verification"
              " through your invitation link!",
          )

      ref_count = get_referral_count(user_id)
      status_str = (
          "💎 PREMIUM ACCESS"
          if has_premium_access(user_id)
          else f"❌ NO PREMIUM"
      )
      welcome_caption = (
          "⚡ <b>NOBITA BAN X UNBAN PREMIUM BOT</b> ⚡\n\n"
          "Welcome! Select an option below to start:\n\n"
          f"👤 <b>Your ID:</b> <code>{user_id}</code>\n"
          f"👑 <b>Status:</b> <b>{status_str}</b>\n"
          f"🚀 <b>Referrals:</b> <code>{ref_count}/{REQUIRED_REFERRALS}</code>"
      )
      send_photo(
          chat_id,
          BANNER_URL,
          welcome_caption,
          reply_markup=get_main_menu_keyboard(user_id),
          parse_mode="HTML",
      )
    else:
      answer_callback_query(callback_id, "❌ Channel not joined yet!")
    return

  if not is_user_joined(user_id):
    return

  ref_count = get_referral_count(user_id)

  if data in [
      "action_perm_ban",
      "action_temp_ban",
      "action_mass_report",
      "action_unban",
  ]:
    if not has_premium_access(user_id):
      answer_callback_query(
          callback_id,
          "NOBITA BAN X UNBAN PREMIUM BOT\nAccess Restricted!",
          show_alert=True,
      )
      lock_msg = (
          "📜 <b>ACCESS DENIED</b>\n\n"
          "You need owner approval to use this command! Get premium below.\n\n"
          "👑 <b>PREMIUM PLANS</b>\n"
          "• <b>3 Days</b> — ⭐ 100 Stars\n"
          "• <b>7 Days</b> — ⭐ 200 Stars\n"
          "• <b>1 Month</b> — 🖼️ 500 Stars\n"
          "• <b>Lifetime</b> — 🖼️ 1 NFT\n\n"
          f"👑 <b>Owner:</b> {OWNER_USERNAME}\n"
          "<i>Click the button below to buy premium.</i>"
      )
      edit_message_text(
          chat_id,
          message_id,
          lock_msg,
          reply_markup=get_buy_premium_keyboard(),
          parse_mode="HTML",
      )
      return

    last_action = get_last_action_time(user_id)
    now = int(time.time())
    time_passed = now - last_action

    if time_passed < COOLDOWN_TIME and user_id != OWNER_ID:
      remaining_seconds = COOLDOWN_TIME - time_passed
      mins = remaining_seconds // 60
      secs = remaining_seconds % 60
      answer_callback_query(callback_id, f"⏳ Cooldown: {mins}m {secs}s left")
      cooldown_msg = (
          "⏳ <b>[ SERVER COOLDOWN ACTIVE ]</b>\n\n"
          "<blockquote>Rate limits are active to safeguard network gateways."
          " Only 1 request allowed per 15 minutes.</blockquote>\n\n"
          f"🕒 <b>Time Remaining:</b> <code>{mins}m {secs}s</code>"
      )
      edit_message_text(
          chat_id,
          message_id,
          cooldown_msg,
          reply_markup=get_back_keyboard(),
          parse_mode="HTML",
      )
      return

  if data == "action_perm_ban":
    answer_callback_query(callback_id, "Permanent Ban Selected")
    edit_message_text(
        chat_id,
        message_id,
        "💥 <b>[ PERMANENT BAN ]</b>\n\n<i>Enter target number with country"
        " code (e.g. +91XXXXXXXXXX):</i>",
        reply_markup=get_back_keyboard(),
        parse_mode="HTML",
    )
    user_states[chat_id] = "perm_ban_input"

  elif data == "action_temp_ban":
    answer_callback_query(callback_id, "Temporary Ban Selected")
    edit_message_text(
        chat_id,
        message_id,
        "⏳ <b>[ TEMPORARY BAN ]</b>\n\n<i>Enter target number with country"
        " code:</i>",
        reply_markup=get_back_keyboard(),
        parse_mode="HTML",
    )
    user_states[chat_id] = "temp_ban_input"

  elif data == "action_mass_report":
    answer_callback_query(callback_id, "Mass Report Selected")
    edit_message_text(
        chat_id,
        message_id,
        "🚨 <b>[ MASS REPORT ]</b>\n\n<i>Enter target number with country"
        " code:</i>",
        reply_markup=get_back_keyboard(),
        parse_mode="HTML",
    )
    user_states[chat_id] = "mass_report_input"

  elif data == "action_unban":
    answer_callback_query(callback_id, "Unban Selected")
    edit_message_text(
        chat_id,
        message_id,
        "🔓 <b>[ UNBAN EXECUTION ]</b>\n\n<i>Enter target number to unban:</i>",
        reply_markup=get_back_keyboard(),
        parse_mode="HTML",
    )
    user_states[chat_id] = "unban_input"

  elif data == "action_get_premium":
    answer_callback_query(callback_id, "VIP Pricing")
    premium_pricing_text = (
        "📜 <b>ACCESS DENIED</b>\n\n"
        "You need owner approval to use this command! Get premium below.\n\n"
        "👑 <b>PREMIUM PLANS</b>\n"
        "• <b>3 Days</b> — ⭐ 100 Stars\n"
        "• <b>7 Days</b> — ⭐ 200 Stars\n"
        "• <b>1 Month</b> — 🖼️ 500 Stars\n"
        "• <b>Lifetime</b> — 🖼️ 1 NFT\n\n"
        f"👑 <b>Owner:</b> {OWNER_USERNAME}\n"
        "<i>Click the button below to buy premium.</i>"
    )
    edit_message_text(
        chat_id,
        message_id,
        premium_pricing_text,
        reply_markup=get_buy_premium_keyboard(),
        parse_mode="HTML",
    )

  elif data == "action_bot_status":
    answer_callback_query(callback_id, "System Online")
    status_text = (
        "⚙️ ─────── <b>[ NETWORK STATUS ]</b> ─────── ⚙️\n\n"
        "┌── 🛡️ <b><u>SYSTEM METRICS</u></b>\n"
        "├ 🟢 <b>API Node:</b> Online & Operational\n"
        "├ ⚡ <b>Latency:</b> 0.012 ms\n"
        "├ 🔒 <b>Security Layer:</b> AES-256 Bit\n"
        "└ 🌐 <b>Active Proxies:</b> 500+ Nodes\n\n"
        "❖ ───────────────────────────── ❖"
    )
    edit_message_text(
        chat_id,
        message_id,
        status_text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML",
    )

  elif data == "action_invite":
    answer_callback_query(callback_id, "Referral Panel")
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    ref_text = (
        "💎 ─────── <b>[ REFERRAL PANEL ]</b> ─────── 💎\n\n"
        "<blockquote>Invite 15 users to unlock full access to all ban & unban"
        " modules.</blockquote>\n\n"
        "┌── 🔗 <b><u>YOUR LINK</u></b>\n"
        f"└ <code>{ref_link}</code>\n\n"
        f"👥 <b>Successful Referrals:</b> <code>{ref_count} /"
        f" {REQUIRED_REFERRALS}</code>\n\n"
        "❖ ───────────────────────────── ❖"
    )
    edit_message_text(
        chat_id,
        message_id,
        ref_text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML",
    )

  elif data == "go_back":
    answer_callback_query(callback_id, "Returning...")
    status_str = (
        "💎 PREMIUM ACCESS"
        if has_premium_access(user_id)
        else f"❌ NO PREMIUM"
    )
    welcome_caption = (
        "⚡ <b>NOBITA BAN X UNBAN PREMIUM BOT</b> ⚡\n\n"
        "Welcome! Select an option below to start:\n\n"
        f"👤 <b>Your ID:</b> <code>{user_id}</code>\n"
        f"👑 <b>Status:</b> <b>{status_str}</b>\n"
        f"🚀 <b>Referrals:</b> <code>{ref_count}/{REQUIRED_REFERRALS}</code>"
    )
    edit_message_text(
        chat_id,
        message_id,
        welcome_caption,
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode="HTML",
    )
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
      response = requests.get(
          API_URL + "/getUpdates",
          params={"timeout": 30, "offset": offset},
          timeout=35,
      ).json()
      if response.get("ok"):
        for update in response["result"]:
          offset = update["update_id"] + 1
          if "message" in update:
            handle_message(update["message"])
          elif "callback_query" in update:
            handle_callback(update["callback_query"])
    except Exception as e:
      time.sleep(1)


def run_server():
  port = int(os.environ.get("PORT", 8080))
  server = HTTPServer(("0.0.0.0", port), WebServer)
  server.serve_forever()


if __name__ == "__main__":
  init_db()
  Thread(target=run_server, daemon=True).start()
  bot_polling()
