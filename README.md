import sys
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from flask import Flask
from threading import Thread

# --- 🌐 WEB SERVER FOR RENDER ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is Running!"

def run_web():
    # Render automatically sets the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- ⚙️ CONFIGURATION ---
API_ID = 37314366
API_HASH = "bd4c934697e7e91942ac911a5a287b46"
BOT_TOKEN = "8484278887:AAEF3HBf2WIi2A2kXKx2B_SNRfcWv5WWmAg"
OWNER_ID = 8448533037
FORCE_CHANNEL = "Anysnapupdate" 
FORCE_GROUP = "Anysnapsupport"

app = Client("SafeHostBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
running_processes = {}

async def check_auth(client, message):
    user_id = message.from_user.id
    if user_id == OWNER_ID:
        return True
    if FORCE_CHANNEL and FORCE_GROUP:
        try:
            await client.get_chat_member(FORCE_CHANNEL, user_id)
            await client.get_chat_member(FORCE_GROUP, user_id)
            return True
        except UserNotParticipant:
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL}")],
                [InlineKeyboardButton("👥 Join Group", url=f"https://t.me/{FORCE_GROUP}")],
                [InlineKeyboardButton("✅ Try Again", url=f"https://t.me/{client.me.username}?start=start")]
            ])
            await message.reply_text("🔒 **Access Denied:** Please join our channels first.", reply_markup=btn)
            return False
        except Exception:
            return True 
    return True

@app.on_message(filters.command("start"))
async def start(client, message):
    if not await check_auth(client, message): return
    await message.reply_text("🤖 **Python Script Manager Active**\nBas `.py` file send karein.")

@app.on_message(filters.command("status"))
async def status(client, message):
    if not await check_auth(client, message): return
    active_bots = [f"🟢 `{f}` (PID: {p.pid})" for f, p in running_processes.items() if p.returncode is None]
    await message.reply_text("**Running Scripts:**\n\n" + "\n".join(active_bots) if active_bots else "💤 No scripts running.")

@app.on_message(filters.command("stop"))
async def stop_script(client, message):
    if not await check_auth(client, message): return
    try:
        filename = message.command[1]
        if filename in running_processes:
            running_processes[filename].terminate()
            del running_processes[filename]
            await message.reply_text(f"🛑 Stopped `{filename}`.")
    except:
        await message.reply_text("⚠️ Usage: `/stop filename.py`")

@app.on_message(filters.document)
async def run_script(client, message):
    if not await check_auth(client, message): return
    if not message.document.file_name.endswith(".py"): return

    file_name = message.document.file_name
    path = await message.download()
    
    try:
        log_out = open(f"{file_name}.log", "w")
        proc = await asyncio.create_subprocess_exec(sys.executable, path, stdout=log_out, stderr=log_out)
        running_processes[file_name] = proc
        await message.reply_text(f"✅ **Started:** `{file_name}`\n📝 Logs: `/logs {file_name}`")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {e}")

if __name__ == "__main__":
    # Web server ko background thread mein start karein
    Thread(target=run_web).start()
    print("✅ Web Server & Bot Starting...")
    app.run()
