import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime, timezone
import requests
import re
import html

# ================== CONFIG ==================
BOT_TOKEN = "7990743595:AAH8aloHTnFVxLdQadQFEKdeL42aALrsy8c"
ADMIN_IDS = [6415960307]

DEFAULT_CREDITS = 50
LOOKUP_COST = 1
VEHICLE_LOOKUP_COST = 1  # cost for vehicle lookup

CHANNEL_ID = -1003470168622
CHANNEL_LINK = "https://t.me/sbhackz"

bot = telebot.TeleBot(BOT_TOKEN)

# ================== CLEAN OUTPUT FORMAT (Number Lookup) ==================
def format_lookup(data):
    if not data.get("success"):
        return "⚠️ No data found."

    upstream = data.get("upstream", {})
    records = upstream.get("data", {}).get("data", [])

    if not records:
        return "⚠️ No records found for this number."

    final_msg = "📱 *Lookup Result*\n━━━━━━━━━━━━━━\n"

    for idx, info in enumerate(records, start=1):
        final_msg += f"🔹 *Record {idx}*\n"
        final_msg += f"👤 Name: `{info.get('name','N/A')}`\n"
        final_msg += f"📞 Mobile: `{info.get('mobile','N/A')}`\n"
        final_msg += f"👨‍👦 Father: `{info.get('father_name','N/A')}`\n"
        final_msg += f"📍 Address: `{info.get('address','N/A')}`\n"
        final_msg += f"🏢 Circle: `{info.get('circle','N/A')}`\n"
        final_msg += f"🆔 ID Number: `{info.get('id_number','N/A')}`\n"
        final_msg += "━━━━━━━━━━━━━━\n"

    final_msg += f"\n⏳ Valid till: `{upstream.get('valid_until','N/A')}`"

    return final_msg

# ================== NUMBER LOOKUP FUNCTION ==================
def lookup_number(mobile_number: str) -> str:
    GENERIC_ERROR = "⚠️ API not working currently, please contact admin."

    try:
        num = mobile_number.strip().replace(" ", "").replace("-", "")

        if not num:
            return "Number khali hai."

        url = f"https://kalyug-papa.vercel.app/api/info?num={num}&key=papabolo"
        resp = requests.get(url, timeout=15)

        if resp.status_code != 200:
            return GENERIC_ERROR

        try:
            data = resp.json()
        except:
            return GENERIC_ERROR

        if not data:
            return "❗ Data Not found ❌."

        return format_lookup(data)

    except:
        return GENERIC_ERROR

# ================== VEHICLE LOOKUP (SAFE) ==================
def sanitize_text(text: str) -> str:
    # remove html tags and unescape entities
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return text.strip()

def lookup_vehicle(reg_no: str) -> str:
    """
    Query vehicle API but return only whitelisted public/non-PII fields.
    If API returns JSON, we will pick only allowed keys.
    If API returns HTML/text, we show a short sanitized preview.
    """
    GENERIC_ERROR = "⚠️ Vehicle API not working currently, please contact admin."

    try:
        num = reg_no.strip().replace(" ", "").upper()
        if not num:
            return "Registration number khali hai."

        url = f"https://earnindia.top/d.php?b={num}"
        resp = requests.get(url, timeout=15)

        if resp.status_code != 200:
            return GENERIC_ERROR

        # Try JSON first
        try:
            data = resp.json()
        except:
            data = None

        # Whitelist of safe fields to display if present in JSON
        whitelist = [
            "owner_name", "father_name", "permanent_address", "is_financed", "rc_status",
            "rto_name", "gross_weight", "brand_name", "brand_model", "manufacturing_date",
            "registration_number", "registration_state", "make-", "model",
            "vehicle_class", "fuel", "registration_date", "registration_year",
            "manufacture_year", "engine_number", "chassis_number", "latest_by",
        ]

        if isinstance(data, dict):
            # Build a safe message using only whitelisted fields
            lines = ["🚗 *Vehicle Lookup Result*","━━━━━━━━━━━━━━"]
            found = False
            for key in whitelist:
                if key in data and data.get(key):
                    val = str(data.get(key))
                    lines.append(f"• *{key.replace('_',' ').title()}:* `{val}`")
                    found = True

            # If the API includes owner-related keys, DO NOT DISPLAY them; instead indicate redacted
            owner_keys = ["owner_name", "owner", "address", "registered_owner"]
            for k in owner_keys:
                if k in data:
                   lines.append("")

            if not found:
                lines.append("⚠️ No non-sensitive vehicle fields found in response.")
            return "\n".join(lines)

        # If not JSON, fallback to sanitized text preview (no PII extraction)
        text = sanitize_text(resp.text)
        preview = text[:1000] if len(text) > 1000 else text
        msg = (
            "🚗 *Vehicle Lookup Result (Raw Preview)*\n"
            "━━━━━━━━━━━━━━\n"
            "⚠️ The API returned non-JSON content. Showing a short sanitized preview below.\n\n"
            f"```\n{preview}\n```\n\n"
            "If this contains owner name or address, those fields are NOT extracted or shown separately by the bot."
        )
        return msg

    except Exception as e:
        # don't leak exception details; return generic
        return GENERIC_ERROR

# ================== DATABASE ==================
conn = sqlite3.connect("bott.db", check_same_thread=False)
cur = conn.cursor()

def ensure_column(table: str, col_def: str):
    col_name = col_def.split()[0]
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if col_name not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
        conn.commit()

def init_db():
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()

    ensure_column("users", "username TEXT")
    ensure_column("users", "credits INTEGER DEFAULT 0")
    ensure_column("users", "referred_by INTEGER")
    ensure_column("users", "is_banned INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query TEXT,
            result TEXT,
            created_at TEXT
        )
    """)
    conn.commit()

init_db()

# ================= HELPERS =================
def get_or_create_user(user_id, username=None, referred_by=None):
    cur.execute("SELECT user_id, username, credits, referred_by, is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    if row:
        if username and row[1] != username:
            cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            conn.commit()
        return row

    cur.execute(
        "INSERT INTO users (user_id, username, credits, referred_by, is_banned) VALUES (?, ?, ?, ?, 0)",
        (user_id, username, DEFAULT_CREDITS, referred_by)
    )
    conn.commit()

    cur.execute("SELECT user_id, username, credits, referred_by, is_banned FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()

def add_credits(user_id, amount):
    cur.execute("UPDATE users SET credits = COALESCE(credits, 0) + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def remove_credits(user_id, amount):
    cur.execute(
        "UPDATE users SET credits = MAX(COALESCE(credits, 0) - ?, 0) WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()

def get_credits(user_id):
    cur.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else 0

def set_ban_status(user_id, status):
    cur.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if status else 0, user_id))
    conn.commit()

def is_banned(user_id):
    cur.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return True if row and row[0] == 1 else False

def save_history(user_id, query, result):
    cur.execute(
        "INSERT INTO history (user_id, query, result, created_at) VALUES (?, ?, ?, ?)",
        (user_id, query, result[:2000], datetime.now(timezone.utc).isoformat())
    )
    conn.commit()

def get_history(user_id, limit=10):
    cur.execute(
        "SELECT query, result, created_at FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )
    return cur.fetchall()

# ================== FORCE SUB ==================
def is_user_in_channel(user_id: int) -> bool:
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def send_force_sub(chat_id: int):
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🔔 Join Channel", url=CHANNEL_LINK))
    kb.row(InlineKeyboardButton("✅ Joined, Check Again", callback_data="check_sub"))

    bot.send_message(
        chat_id,
        "🤖 Bot use karne ke liye channel join karein.\n\n"
        "Join karne ke baad 'Check Again' dabayein.",
        reply_markup=kb
    )

def ensure_user_record_from_obj(obj):
    get_or_create_user(obj.id, username=obj.username or "unknown")

# ================== UI ==================
def main_menu(is_admin=False):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("🔍 Number Lookup", callback_data="number_info"),
        InlineKeyboardButton("🚗 Vehicle Lookup", callback_data="vehicle_info")
    )
    kb.row(
        InlineKeyboardButton("🎁 Referral", callback_data="referral"),
        InlineKeyboardButton("💳 Credits", callback_data="my_credits"),
    )
    kb.row(
        InlineKeyboardButton("📜 My History", callback_data="my_history"),
    )
    if is_admin:
        kb.row(InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel"))
    return kb

# ================== /addcredit COMMAND (ONLY ADMIN) ==================
@bot.message_handler(commands=['addcredit'])
def add_credit_step1(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ You are not admin.")
        return

    bot.reply_to(message, "👤 Username bhejo (without @). Example: sbhackz")
    bot.register_next_step_handler(message, add_credit_step2)

def add_credit_step2(message):
    username = message.text.strip().replace("@", "")
    cur.execute("SELECT user_id, credits FROM users WHERE username = ?", (username,))
    row = cur.fetchone()

    if not row:
        bot.reply_to(message, "❌ Username database me nahi mila.")
        return

    uid = row[0]
    bot.reply_to(message, f"💰 Kitne credits add karna hai @{username}?")
    bot.register_next_step_handler(message, add_credit_step3, uid, username)

def add_credit_step3(message, uid, username):
    try:
        amount = int(message.text)
    except:
        bot.reply_to(message, "❌ Credits number me doitna.")
        return

    add_credits(uid, amount)
    bot.reply_to(
        message,
        f"✅ Credit Added Successfully!\n"
        f"👤 User: @{username}\n"
        f"🆔 ID: {uid}\n"
        f"💳 New Balance: {get_credits(uid)}"
    )

# ================== START COMMAND ==================
@bot.message_handler(commands=["start"])
def start_cmd(message):
    user_id = message.from_user.id

    if not is_user_in_channel(user_id):
        send_force_sub(message.chat.id)
        return

    username = message.from_user.username or "unknown"

    # Referral
    args = message.text.split()
    referred_by = None
    if len(args) > 1:
        try:
            ref = int(args[1])
            if ref != user_id:
                referred_by = ref
        except:
            pass

    get_or_create_user(user_id, username, referred_by)

    bot.send_message(
        message.chat.id,
        f"🙏🏻 Welcome {message.from_user.first_name}!\n\nChoose an option 👇",
        reply_markup=main_menu(user_id in ADMIN_IDS)
    )

# ================== CALLBACK ==================
USER_STATE = {}

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "check_sub":
        if is_user_in_channel(user_id):
            ensure_user_record_from_obj(call.from_user)
            bot.send_message(call.message.chat.id, "✅ Verified!", reply_markup=main_menu(user_id in ADMIN_IDS))
        else:
            send_force_sub(call.message.chat.id)
        return

    if not is_user_in_channel(user_id):
        send_force_sub(call.message.chat.id)
        return

    ensure_user_record_from_obj(call.from_user)

    if data == "number_info":
        USER_STATE[user_id] = "awaiting_number"
        bot.send_message(call.message.chat.id, "📞 Number bhejo:")

    elif data == "vehicle_info":
        USER_STATE[user_id] = "awaiting_vehicle"
        bot.send_message(call.message.chat.id,
                         "🚗 Vehicle registration bhejo (Example: MP09MZ4310)\n\n"
                         "»📱 Instagram : sandeep._.op")

    elif data == "my_credits":
        bot.send_message(call.message.chat.id, f"💳 Credits: {get_credits(user_id)}")

    elif data == "referral":
        link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        bot.send_message(call.message.chat.id, f"🎁 Referral Link:\n{link}")

    elif data == "my_history":
        rows = get_history(user_id)
        if not rows:
            bot.send_message(call.message.chat.id, "📜 No history found.")
        else:
            txt = "📜 Your Lookups:\n\n"
            for q, r, dt in rows:
                txt += f"- {q} @ {dt}\n"
            bot.send_message(call.message.chat.id, txt)

    elif data == "admin_panel":
        if user_id not in ADMIN_IDS:
            bot.send_message(call.message.chat.id, "❌ Not admin.")
            return
        bot.send_message(call.message.chat.id, "🛠 Admin Commands:\n\nUse: /addcredit", reply_markup=main_menu(True))

# ================== LOOKUP HANDLERS ==================
@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id) == "awaiting_number")
def handle_lookup(message):
    user_id = message.from_user.id
    number = message.text.strip()

    # Check credits
    if get_credits(user_id) < LOOKUP_COST:
        bot.send_message(message.chat.id, "❌ Not enough credits.")
        USER_STATE[user_id] = None
        return

    bot.send_message(message.chat.id, "⌛ Processing…")

    result = lookup_number(number)

    # ❗ Check if API failed → NO CREDIT CUT
    if "⚠️" in result or "❗" in result or "No data" in result:
        bot.send_message(message.chat.id, "⚠️ Server down, please try again later.\n💳 No credits deducted.")
        USER_STATE[user_id] = None
        return

    # SUCCESS → cut credits
    remove_credits(user_id, LOOKUP_COST)
    save_history(user_id, number, result)

    msg = (
        "✅ Lookup Complete\n━━━━━━━━━━━━━━\n"
        f"📱 Number: {number}\n\n"
        f"{result}"
    )

    bot.send_message(message.chat.id, msg, parse_mode="Markdown")
    bot.send_message(message.chat.id, f"💳 Remaining Credits: {get_credits(user_id)}")

    USER_STATE[user_id] = None

@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id) == "awaiting_vehicle")
def handle_vehicle_lookup(message):
    user_id = message.from_user.id
    reg = message.text.strip().upper()

    if get_credits(user_id) < VEHICLE_LOOKUP_COST:
        bot.send_message(message.chat.id, "❌ Not enough credits.")
        USER_STATE[user_id] = None
        return

    bot.send_message(message.chat.id, "⌛ Searching in database...")

    result = lookup_vehicle(reg)

    # ❗ If API failed → no credit cut
    if "⚠️" in result:
        bot.send_message(message.chat.id, "⚠️ Server down, please try again later.\n💳 No credits deducted.")
        USER_STATE[user_id] = None
        return

    # SUCCESS → Deduct credit
    remove_credits(user_id, VEHICLE_LOOKUP_COST)
    save_history(user_id, reg, result)

    msg = (
        "✅ Vehicle Lookup Complete\n━━━━━━━━━━━━━━\n"
        f"🚘 Registration: {reg}\n\n"
        f"{result}"
    )

    bot.send_message(message.chat.id, msg, parse_mode="Markdown")
    bot.send_message(message.chat.id, f"💳 Remaining Credits: {get_credits(user_id)}")

    USER_STATE[user_id] = None

# ================== FALLBACK ==================
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "🙂 Use /start")

# ================== RUN ==================
print("Bot is running…")
bot.infinity_polling()
