# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import logging
import threading
import sys
import re

# --- Flask Keep Alive (Render ke liye Zaroori) ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I am Alive! F4X Host Bot is Running."

def run_flask():
    # Render automatically assigns a PORT env variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
# --- End Flask Keep Alive ---

# --- Configuration ---
TOKEN = '8484278887:AAGKj_DeQhObncIwrwc05pDbVV-f2dZPxhE'
OWNER_ID = 8448533037
ADMIN_ID = 8448533037
YOUR_USERNAME = '@f4x_empire'
UPDATE_CHANNEL = 'https://t.me/f4x_empirebot'

# Directories
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

# Limits
FREE_USER_LIMIT = 10
SUBSCRIBED_USER_LIMIT = 50
ADMIN_LIMIT = 999

# Ensure Directories Exist
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

# Initialize Bot
bot = telebot.TeleBot(TOKEN)

# --- Global Variables ---
bot_scripts = {}  # To store running processes
user_files = {}   # In-memory file cache
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False
start_time = time.time()

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database Management ---
def init_db():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_files (user_id INTEGER, file_name TEXT, file_type TEXT, PRIMARY KEY (user_id, file_name))''')
    c.execute('''CREATE TABLE IF NOT EXISTS active_users (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def load_data():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # Load Files
    c.execute('SELECT user_id, file_name FROM user_files')
    for uid, fname in c.fetchall():
        if uid not in user_files: user_files[uid] = []
        user_files[uid].append((fname, 'python'))
        
    # Load Users (Fix for Broadcast)
    c.execute('SELECT user_id FROM active_users')
    rows = c.fetchall()
    for row in rows:
        active_users.add(row[0])
    
    logger.info(f"Loaded {len(active_users)} users from database.")
    conn.close()

# Initialize DB
init_db()
load_data()

# --- Helper Functions ---
def get_user_folder(user_id):
    path = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

def save_user_to_db(user_id):
    if user_id not in active_users:
        active_users.add(user_id)
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB Error: {e}")

# --- Keyboards ---
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    btn1 = types.KeyboardButton("📢 Updates Channel")
    btn2 = types.KeyboardButton("📤 Upload File")
    btn3 = types.KeyboardButton("📂 Check Files")
    btn4 = types.KeyboardButton("⚡ Bot Speed")
    btn5 = types.KeyboardButton("📊 Statistics")
    
    if user_id in admin_ids:
        # Admin Buttons
        btn6 = types.KeyboardButton("💳 Subscriptions")
        btn7 = types.KeyboardButton("📢 Broadcast")
        btn8 = types.KeyboardButton("🔒 Lock Bot")
        btn9 = types.KeyboardButton("🟢 Running All Code")
        btn10 = types.KeyboardButton("📤 Send Command")
        btn11 = types.KeyboardButton("👑 Admin Panel")
        btn12 = types.KeyboardButton("📞 Contact Owner")
        
        markup.add(btn1)
        markup.add(btn2, btn3)
        markup.add(btn4, btn5)
        markup.add(btn6, btn7)
        markup.add(btn8, btn9)
        markup.add(btn10, btn11)
        markup.add(btn12)
    else:
        # User Buttons
        btn_contact = types.KeyboardButton("📞 Contact Owner")
        markup.add(btn1)
        markup.add(btn2, btn3)
        markup.add(btn4, btn5)
        markup.add(types.KeyboardButton("📤 Send Command"), btn_contact)
        
    return markup

# ==========================================
#          ALL BUTTON HANDLERS
# ==========================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    save_user_to_db(user_id)
    bot.reply_to(message, f"👋 Welcome to **F4X Host Bot**!\n\nI can host your Python files 24/7.", 
                 reply_markup=main_menu(user_id), parse_mode='Markdown')

# 1. Updates Channel
@bot.message_handler(func=lambda m: m.text == "📢 Updates Channel")
def updates_channel(message):
    bot.reply_to(message, f"📢 Click here to join updates channel:\n{UPDATE_CHANNEL}")

# 2. Contact Owner (FIXED: Removed parse_mode to handle underscores correctly)
@bot.message_handler(func=lambda m: m.text == "📞 Contact Owner")
def contact_owner(message):
    bot.reply_to(message, f"📞 Owner: {YOUR_USERNAME}\nDM for support or purchase.")

# 3. Statistics
@bot.message_handler(func=lambda m: m.text == "📊 Statistics")
def statistics(message):
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    uptime = str(timedelta(seconds=int(time.time() - start_time)))
    total_scripts = len(bot_scripts)
    
    msg = (f"📊 **Bot Statistics**\n"
           f"━━━━━━━━━━━━━━━━\n"
           f"💻 CPU: {cpu}%\n"
           f"💾 RAM: {ram}%\n"
           f"👥 Users: {len(active_users)}\n"
           f"🟢 Running Scripts: {total_scripts}\n"
           f"⏰ Uptime: {uptime}")
    bot.reply_to(message, msg, parse_mode='Markdown')

# 4. Bot Speed
@bot.message_handler(func=lambda m: m.text == "⚡ Bot Speed")
def bot_speed(message):
    start = time.time()
    msg = bot.send_message(message.chat.id, "⚡ Checking speed...")
    end = time.time()
    ping = int((end - start) * 1000)
    bot.edit_message_text(f"⚡ **Bot Speed:** {ping}ms\n🚀 Server is running smoothly!", message.chat.id, msg.message_id, parse_mode='Markdown')

# 5. Upload File
@bot.message_handler(func=lambda m: m.text == "📤 Upload File")
def upload_file(message):
    if bot_locked and message.from_user.id not in admin_ids:
        bot.reply_to(message, "🔒 Bot is currently locked by Admin.")
        return
    bot.reply_to(message, "📂 **Send me your Python file (.py)** now.", parse_mode='Markdown')

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        if bot_locked and message.from_user.id not in admin_ids:
            return
            
        user_id = message.from_user.id
        save_user_to_db(user_id) # Ensure user is saved
        file_name = message.document.file_name
        
        if not file_name.endswith('.py'):
            bot.reply_to(message, "❌ Only `.py` files allowed!")
            return
            
        # Download
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        # Save
        folder = get_user_folder(user_id)
        path = os.path.join(folder, file_name)
        with open(path, 'wb') as f:
            f.write(downloaded)
            
        # Update DB & Memory
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)', 
                  (user_id, file_name, 'python'))
        conn.commit()
        conn.close()
        
        if user_id not in user_files: user_files[user_id] = []
        user_files[user_id].append((file_name, 'python'))
        
        bot.reply_to(message, f"✅ **File Saved:** `{file_name}`\nUse '📂 Check Files' to run it.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# 6. Check Files
@bot.message_handler(func=lambda m: m.text == "📂 Check Files")
def check_files(message):
    user_id = message.from_user.id
    files = user_files.get(user_id, [])
    
    if not files:
        bot.reply_to(message, "❌ You have no uploaded files.")
        return
        
    markup = types.InlineKeyboardMarkup()
    for fname, ftype in files:
        markup.add(types.InlineKeyboardButton(f"▶ Run {fname}", callback_data=f"run_{fname}"),
                   types.InlineKeyboardButton(f"🗑 Delete {fname}", callback_data=f"del_{fname}"))
                   
    bot.reply_to(message, "📂 **Your Files:**", reply_markup=markup)

# --- Callback Handlers ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    folder = get_user_folder(user_id)
    
    if data.startswith("run_"):
        filename = data.split("run_")[1]
        filepath = os.path.join(folder, filename)
        key = f"{user_id}_{filename}"
        
        if key in bot_scripts:
            bot.answer_callback_query(call.id, "Already running!")
            return
            
        try:
            log_path = os.path.join(folder, f"{filename}.log")
            log_file = open(log_path, "a")
            # Using subprocess to run independently
            proc = subprocess.Popen([sys.executable, filepath], cwd=folder, stdout=log_file, stderr=log_file)
            bot_scripts[key] = {'proc': proc, 'log': log_file, 'name': filename}
            bot.answer_callback_query(call.id, "Script Started!")
            bot.send_message(call.message.chat.id, f"✅ **Started:** `{filename}` (PID: {proc.pid})", parse_mode='Markdown')
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Failed: {e}")

    elif data.startswith("del_"):
        filename = data.split("del_")[1]
        filepath = os.path.join(folder, filename)
        try:
            if os.path.exists(filepath): os.remove(filepath)
            # Remove from DB
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM user_files WHERE user_id=? AND file_name=?", (user_id, filename))
            conn.commit()
            conn.close()
            # Update Memory
            user_files[user_id] = [f for f in user_files.get(user_id, []) if f[0] != filename]
            bot.answer_callback_query(call.id, "Deleted!")
            bot.edit_message_text(f"🗑 `{filename}` deleted.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}")

# ==========================================
#          ADMIN ONLY BUTTONS
# ==========================================

# 7. Admin Panel
@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel(message):
    if message.from_user.id not in admin_ids: return
    bot.reply_to(message, "👑 **Admin Panel Active**\nSelect an option from the keyboard.")

# 8. Lock Bot
@bot.message_handler(func=lambda m: m.text == "🔒 Lock Bot")
def lock_bot(message):
    if message.from_user.id not in admin_ids: return
    global bot_locked
    bot_locked = not bot_locked
    status = "LOCKED 🔒" if bot_locked else "UNLOCKED 🔓"
    bot.reply_to(message, f"✅ Bot is now **{status}**.", parse_mode='Markdown')

# 9. Running All Code
@bot.message_handler(func=lambda m: m.text == "🟢 Running All Code")
def running_all_code(message):
    if message.from_user.id not in admin_ids: return
    if not bot_scripts:
        bot.reply_to(message, "🚫 No scripts are currently running.")
        return
        
    msg = "🟢 **All Running Scripts:**\n"
    for key, info in bot_scripts.items():
        uid = key.split('_')[0]
        msg += f"👤 User: `{uid}` | 📄 File: `{info['name']}` | PID: `{info['proc'].pid}`\n"
    
    bot.reply_to(message, msg, parse_mode='Markdown')

# 10. Subscriptions
@bot.message_handler(func=lambda m: m.text == "💳 Subscriptions")
def subscriptions(message):
    if message.from_user.id not in admin_ids: return
    bot.reply_to(message, "💳 **Subscription Management**\nTo add user: `/add_sub <user_id> <days>`\nTo remove: `/rem_sub <user_id>`", parse_mode='Markdown')

@bot.message_handler(commands=['add_sub'])
def add_sub(message):
    if message.from_user.id not in admin_ids: return
    try:
        args = message.text.split()
        uid = int(args[1])
        days = int(args[2])
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
        
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)", (uid, expiry))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Added subscription for User `{uid}` for {days} days.", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Usage: `/add_sub user_id days`")

# 11. Broadcast
@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def broadcast_ask(message):
    if message.from_user.id not in admin_ids: return
    msg = bot.reply_to(message, "📝 **Send the message to broadcast:**")
    bot.register_next_step_handler(msg, perform_broadcast)

def perform_broadcast(message):
    if message.content_type != 'text':
        bot.reply_to(message, "❌ Broadcast cancelled. Text only.")
        return
        
    count = 0
    total = len(active_users)
    sent_msg = bot.reply_to(message, f"📢 Starting broadcast to {total} users...")
    
    for uid in active_users:
        try:
            bot.send_message(uid, f"📢 **Broadcast:**\n\n{message.text}", parse_mode='Markdown')
            count += 1
            time.sleep(0.05)
        except Exception as e:
            pass
            
    bot.edit_message_text(f"✅ Broadcast complete.\nSent to {count}/{total} users.", 
                          sent_msg.chat.id, sent_msg.message_id)

# 12. Send Command
@bot.message_handler(func=lambda m: m.text == "📤 Send Command")
def send_command_prompt(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "❌ Only Admins can use Shell Commands.")
        return
    bot.reply_to(message, "💻 **Enter Terminal Command:**", parse_mode='Markdown')
    bot.register_next_step_handler(message, execute_shell)

def execute_shell(message):
    if message.from_user.id not in admin_ids: return
    try:
        result = subprocess.check_output(message.text, shell=True, stderr=subprocess.STDOUT)
        output = result.decode('utf-8')
        if len(output) > 4000:
            with open("output.txt", "w") as f: f.write(output)
            with open("output.txt", "rb") as f: bot.send_document(message.chat.id, f)
        else:
            bot.reply_to(message, f"```\n{output}\n```", parse_mode='Markdown')
    except subprocess.CalledProcessError as e:
        bot.reply_to(message, f"❌ Error:\n{e.output.decode()}", parse_mode='Markdown')

# --- Start the Bot ---
if __name__ == "__main__":
    keep_alive() # Starts Flask Server for Render
    logger.info("Bot Started...")
    print("✅ F4X Empire Bot is Ready for Render!")
    bot.infinity_polling(skip_pending=True)
