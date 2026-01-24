import sys
import asyncio
import time
import os
import signal
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

# --- ⚙️ CONFIGURATION ⚙️ ---
API_ID = 37314366
API_HASH = "bd4c934697e7e91942ac911a5a287b46"
BOT_TOKEN = "8484278887:AAEF3HBf2WIi2A2kXKx2B_SNRfcWv5WWmAg"

# 👑 OWNER ID (Sirf Aap Use Kar Payenge)
OWNER_ID = 8448533037  # Yahan apna ID dalein

# 📢 OPTIONAL: Force Sub (Agar chahiye to variables bharein, nahi to blank chhod dein)
FORCE_CHANNEL = "Anysnapupdate" 
FORCE_GROUP = "Anysnapsupport"

app = Client("SafeHostBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 💾 PROCESS MANAGER ---
running_processes = {}  # Store process objects: {filename: process}

async def check_auth(client, message):
    """
    Checks if user is Owner OR Joined Channels.
    Owner is always allowed.
    """
    user_id = message.from_user.id
    
    # 1. Owner Bypass
    if user_id == OWNER_ID:
        return True

    # 2. Check Force Sub (Agar Configured Hai)
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
            return True # Error aayi to allow kar do (Fail-safe)
    
    return True

# --- 🕹️ COMMANDS ---

@app.on_message(filters.command("start"))
async def start(client, message):
    if not await check_auth(client, message):
        return

    await message.reply_text(
        "🤖 **Python Script Manager**\n\n"
        "Main Python scripts ko run kar sakta hoon.\n"
        "Bas `.py` file send karein.\n\n"
        "⚙️ **Commands:**\n"
        "• `/status` - Check running scripts\n"
        "• `/stop <filename>` - Stop a script\n"
        "• `/logs <filename>` - View logs"
    )

@app.on_message(filters.command("status"))
async def status(client, message):
    if not await check_auth(client, message):
        return

    active_bots = []
    
    # Clean up dead processes first
    for file, proc in list(running_processes.items()):
        if proc.returncode is not None:
            del running_processes[file]
        else:
            active_bots.append(f"🟢 `{file}` (PID: {proc.pid})")
            
    if not active_bots:
        await message.reply_text("💤 No scripts are running.")
    else:
        await message.reply_text("**Running Scripts:**\n\n" + "\n".join(active_bots))

@app.on_message(filters.command("stop"))
async def stop_script(client, message):
    if not await check_auth(client, message):
        return

    try:
        filename = message.command[1]
        if filename in running_processes:
            proc = running_processes[filename]
            proc.terminate()
            del running_processes[filename]
            await message.reply_text(f"🛑 Stopped `{filename}`.")
        else:
            await message.reply_text("❌ Script not found running.")
    except IndexError:
        await message.reply_text("⚠️ Usage: `/stop filename.py`")

@app.on_message(filters.command("logs"))
async def get_logs(client, message):
    if not await check_auth(client, message):
        return

    try:
        filename = message.command[1]
        log_file = f"{filename}.log"
        
        if os.path.exists(log_file):
            await message.reply_document(log_file, caption=f"📄 Logs: `{filename}`")
        else:
            await message.reply_text("❌ Log file not found.")
    except IndexError:
        await message.reply_text("⚠️ Usage: `/logs filename.py`")

# --- 🚀 FILE RUNNER (Clean Method) ---

@app.on_message(filters.document)
async def run_script(client, message):
    if not await check_auth(client, message):
        return

    if not message.document.file_name.endswith(".py"):
        await message.reply_text("⚠️ Only `.py` files allowed.")
        return

    file_name = message.document.file_name
    
    # Check if already running
    if file_name in running_processes:
        await message.reply_text(f"⚠️ `{file_name}` is already running! Use `/stop` first.")
        return

    msg = await message.reply_text(f"📥 Downloading `{file_name}`...")
    path = await message.download()

    try:
        # Standard Subprocess (No Shell=True, No Hidden Tricks)
        # Security Note: Hum seedha Python interpreter call kar rahe hain
        log_out = open(f"{file_name}.log", "w")
        
        proc = await asyncio.create_subprocess_exec(
            sys.executable, path,
            stdout=log_out,
            stderr=log_out
        )
        
        running_processes[file_name] = proc
        
        await msg.edit(
            f"✅ **Started Successfully!**\n\n"
            f"📄 File: `{file_name}`\n"
            f"🔧 PID: `{proc.pid}`\n"
            f"📝 Logs: `/logs {file_name}`"
        )
        
    except Exception as e:
        await msg.edit(f"❌ **Error:** {e}")

print("✅ Bot Started Successfully...")
app.run()
