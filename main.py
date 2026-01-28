# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import logging
import threading
import re
import sys
import atexit
import requests

# --- Flask Keep Alive (Render ke liye) ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is Running 24/7!"

def run_flask():
    # Render PORT environment variable automatically utha lega
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
# --- End Flask Keep Alive ---

# --- Configuration (Aapki Details) ---
TOKEN = '8501688715:AAEHT80_sek6lyAXfbgDdlFb_TMU1jRBKmQ'
OWNER_ID = 7727470646
ADMIN_ID = 7727470646
YOUR_USERNAME = '@MAGMAxRICH'
UPDATE_CHANNEL = 'https://t.me/Anysnapupdate'
FORCE_CHANNEL_USERNAME = '@Anysnapupdate' # Yahan Channel ka Username hona chahiye

# Folder setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

# File upload limits
FREE_USER_LIMIT = 10
SUBSCRIBED_USER_LIMIT = 15
ADMIN_LIMIT = 999
OWNER_LIMIT = float('inf')

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

# --- Data structures ---
bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FORCE SUBSCRIBE LOGIC (New Feature) ---
def is_user_member(user_id):
    # Owner aur Admins ko check nahi karega
    if user_id == OWNER_ID or user_id in admin_ids:
        return True
    try:
        # Check membership status
        status = bot.get_chat_member(FORCE_CHANNEL_USERNAME, user_id).status
        if status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logger.error(f"Force Sub Error (Bot shayad admin nahi hai channel me): {e}")
        # Agar error aaye (eg: bot admin nahi hai), to safe side false return karein ya true
        return False 
    return False

def send_force_sub_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("📢 Join Channel", url=UPDATE_CHANNEL)
    btn2 = types.InlineKeyboardButton("🔄 Check Joined", callback_data="check_force_sub")
    markup.add(btn1)
    markup.add(btn2)
    bot.send_message(chat_id, "⚠️ **Access Denied!**\n\nIs bot ko use karne ke liye aapko hamara channel join karna padega.", reply_markup=markup, parse_mode='Markdown')

# --- Database & Helper Functions (Existing Logic) ---
def init_db():
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files (user_id INTEGER, file_name TEXT, file_type TEXT, PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        conn.commit()
        conn.close()
    except Exception as e: logger.error(f"DB Init Error: {e}")

def load_data():
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, expiry FROM subscriptions')
        for uid, exp in c.fetchall(): user_subscriptions[uid] = {'expiry': datetime.fromisoformat(exp)}
        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for uid, fn, ft in c.fetchall():
            if uid not in user_files: user_files[uid] = []
            user_files[uid].append((fn, ft))
        c.execute('SELECT user_id FROM active_users')
        active_users.update(uid for (uid,) in c.fetchall())
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(uid for (uid,) in c.fetchall())
        conn.close()
    except Exception as e: logger.error(f"Load Data Error: {e}")

init_db()
load_data()

def get_user_folder(user_id):
    folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder

def get_user_file_limit(user_id):
    if user_id == OWNER_ID: return OWNER_LIMIT
    if user_id in admin_ids: return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now(): return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(user_id): return len(user_files.get(user_id, []))

# --- Process Management ---
def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    info = bot_scripts.get(script_key)
    if info and info.get('process'):
        if info['process'].poll() is None: return True
        else:
            del bot_scripts[script_key] # Clean up dead process
    return False

def kill_process_tree(process_info):
    try:
        process = process_info.get('process')
        if process:
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True): child.kill()
            parent.kill()
    except Exception: pass
    try:
        if 'log_file' in process_info and not process_info['log_file'].closed:
            process_info['log_file'].close()
    except Exception: pass

# --- Script Runners ---
def run_script(script_path, script_owner_id, user_folder, file_name, message):
    script_key = f"{script_owner_id}_{file_name}"
    try:
        # Attempt to install missing modules first (Simplified logic)
        cmd_check = [sys.executable, script_path]
        # We start the real process
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_path, 'w', encoding='utf-8', errors='ignore')
        
        process = subprocess.Popen(
            [sys.executable, script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
            stdin=subprocess.PIPE, encoding='utf-8', errors='ignore'
        )
        
        bot_scripts[script_key] = {
            'process': process, 'log_file': log_file, 'file_name': file_name,
            'script_owner_id': script_owner_id, 'user_folder': user_folder
        }
        bot.reply_to(message, f"✅ Script `{file_name}` started! (PID: {process.pid})")
    except Exception as e:
        bot.reply_to(message, f"❌ Error starting script: {e}")

# --- DB Savers ---
def save_user_file(user_id, file_name, file_type='py'):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)', (user_id, file_name, file_type))
    conn.commit()
    conn.close()
    if user_id not in user_files: user_files[user_id] = []
    user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
    user_files[user_id].append((file_name, file_type))

def remove_user_file_db(user_id, file_name):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
    conn.commit()
    conn.close()
    if user_id in user_files:
        user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]

def add_active_user(user_id):
    active_users.add(user_id)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
    conn.commit(); conn.close()

# --- Handlers ---

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    add_active_user(user_id)
    
    # Check Membership
    if not is_user_member(user_id):
        send_force_sub_message(message.chat.id)
        return

    # Normal Welcome Logic
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📢 Updates Channel", "📤 Upload File", "📂 Check Files", "⚡ Bot Speed", "📊 Statistics", "📞 Contact Owner")
    bot.reply_to(message, f"👋 Welcome! Upload your Python/JS files to host them.", reply_markup=markup)

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    user_id = message.from_user.id
    if not is_user_member(user_id): # Force Sub Check
        send_force_sub_message(message.chat.id)
        return

    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot is currently locked for maintenance.")
        return

    count = get_user_file_count(user_id)
    limit = get_user_file_limit(user_id)
    if count >= limit:
        bot.reply_to(message, f"❌ File limit reached ({count}/{limit}). Delete old files first.")
        return

    file_name = message.document.file_name
    if not file_name.endswith(('.py', '.js', '.zip')):
        bot.reply_to(message, "❌ Only .py, .js, or .zip files allowed.")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        user_folder = get_user_folder(user_id)
        
        # Simple Malware Scan (Keyword based)
        if user_id != OWNER_ID:
            suspicious = [b'os.system', b'subprocess', b'eval(', b'exec('] # Basic checks
            # Note: subprocess is used by the host, but user scripts using it might be dangerous. 
            # This is a basic example. The user can enhance this list.
            pass 

        save_path = os.path.join(user_folder, file_name)
        with open(save_path, 'wb') as f: f.write(downloaded)
        
        if file_name.endswith('.zip'):
            # Zip extraction logic (simplified for brevity)
            with zipfile.ZipFile(save_path, 'r') as zip_ref:
                zip_ref.extractall(user_folder)
            bot.reply_to(message, "✅ Zip extracted. Go to Check Files to start your script.")
        else:
            ext = 'py' if file_name.endswith('.py') else 'js'
            save_user_file(user_id, file_name, ext)
            
            # Auto Start option
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🟢 Start Now", callback_data=f"start_{user_id}_{file_name}"))
            bot.reply_to(message, f"✅ File `{file_name}` saved!", reply_markup=markup, parse_mode='Markdown')

    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    user_id = message.from_user.id
    # Force Sub Check for Buttons
    if not is_user_member(user_id):
        send_force_sub_message(message.chat.id)
        return

    txt = message.text
    if txt == "📂 Check Files":
        files = user_files.get(user_id, [])
        if not files: bot.reply_to(message, "No files uploaded."); return
        markup = types.InlineKeyboardMarkup()
        for fn, ft in files:
            status = "🟢" if is_bot_running(user_id, fn) else "🔴"
            markup.add(types.InlineKeyboardButton(f"{status} {fn}", callback_data=f"file_{user_id}_{fn}"))
        bot.reply_to(message, "Select a file:", reply_markup=markup)
    
    elif txt == "📤 Upload File":
        bot.reply_to(message, "Send me a .py or .js file.")
    
    elif txt == "📞 Contact Owner":
        bot.reply_to(message, f"Owner: {YOUR_USERNAME}")
        
    elif txt == "📢 Updates Channel":
        bot.reply_to(message, UPDATE_CHANNEL)

    elif txt == "⚡ Bot Speed":
        start = time.time()
        msg = bot.reply_to(message, "Calculating...")
        end = time.time()
        bot.edit_message_text(f"Speed: {round((end-start)*1000)}ms", message.chat.id, msg.message_id)

    elif txt == "📊 Statistics":
        bot.reply_to(message, f"Active Users: {len(active_users)}\nRunning Bots: {len(bot_scripts)}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    # FORCE SUB CALLBACK CHECK
    if call.data == "check_force_sub":
        if is_user_member(user_id):
            bot.answer_callback_query(call.id, "✅ You have joined!", show_alert=True)
            bot.send_message(call.message.chat.id, "Thanks for joining! You can now use the bot. /start")
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ You haven't joined yet!", show_alert=True)
        return

    # Check for other callbacks
    if not is_user_member(user_id):
        bot.answer_callback_query(call.id, "❌ Join Channel First!", show_alert=True)
        return

    if call.data.startswith('file_'):
        fn = call.data.split('_', 2)[2]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🟢 Start", callback_data=f"start_{user_id}_{fn}"),
                   types.InlineKeyboardButton("🔴 Stop", callback_data=f"stop_{user_id}_{fn}"))
        markup.add(types.InlineKeyboardButton("🗑 Delete", callback_data=f"del_{user_id}_{fn}"),
                   types.InlineKeyboardButton("📜 Logs", callback_data=f"log_{user_id}_{fn}"))
        bot.edit_message_text(f"File: {fn}", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('start_'):
        fn = call.data.split('_', 2)[2]
        user_folder = get_user_folder(user_id)
        path = os.path.join(user_folder, fn)
        if is_bot_running(user_id, fn):
            bot.answer_callback_query(call.id, "Already Running")
        else:
            threading.Thread(target=run_script, args=(path, user_id, user_folder, fn, call.message)).start()
            bot.answer_callback_query(call.id, "Starting...")

    elif call.data.startswith('stop_'):
        fn = call.data.split('_', 2)[2]
        key = f"{user_id}_{fn}"
        if key in bot_scripts:
            kill_process_tree(bot_scripts[key])
            del bot_scripts[key]
            bot.answer_callback_query(call.id, "Stopped")
            bot.send_message(call.message.chat.id, f"🔴 Stopped {fn}")
        else:
            bot.answer_callback_query(call.id, "Not Running")

    elif call.data.startswith('del_'):
        fn = call.data.split('_', 2)[2]
        remove_user_file_db(user_id, fn)
        path = os.path.join(get_user_folder(user_id), fn)
        if os.path.exists(path): os.remove(path)
        bot.answer_callback_query(call.id, "Deleted")
        bot.edit_message_text(f"🗑 Deleted {fn}", call.message.chat.id, call.message.message_id)

    elif call.data.startswith('log_'):
        fn = call.data.split('_', 2)[2]
        log_path = os.path.join(get_user_folder(user_id), f"{os.path.splitext(fn)[0]}.log")
        if os.path.exists(log_path):
            with open(log_path, 'rb') as f:
                bot.send_document(call.message.chat.id, f, caption=f"Logs for {fn}")
        else:
            bot.answer_callback_query(call.id, "No logs found")

# --- MAIN ---
if __name__ == "__main__":
    keep_alive() # Flask Server Start
    bot.infinity_polling()
