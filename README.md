import os
import yt_dlp
import asyncio
import uuid
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# --- 1. KEEP-ALIVE SYSTEM ---
app_web = Flask('')
@app_web.route('/')
def home():
    return "🔥 Naeem bhai, F4X Empire is LIVE!"

def run_web():
    app_web.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- 2. CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8421035286:AAHAXb-OI-kqiQnM7UL42o1JervTtQFT9fg"
OWNER_TAG = "👑 Owner: Naeem (F4X Empire)"

def download_engine(url, mode, format_id=None):
    unique_id = str(uuid.uuid4())[:8]
    file_template = f"f4x_{unique_id}.%(ext)s"
    
    ydl_opts = {
        'outtmpl': file_template,
        'noplaylist': True,
        'quiet': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }

    if mode == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'm4a'}]
    else:
        # Replit cloud server high-res video merge kar lega
        ydl_opts['format'] = f"{format_id}+bestaudio/best" if format_id else 'bestvideo+bestaudio/best'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

async def start(update, context):
    await update.message.reply_text(f"🔥 **F4X Cloud Bot Ready!**\n\nNaeem bhai, link bhejien ya gane ka naam likhein.\n\n{OWNER_TAG}")

async def handle_message(update, context):
    query = update.message.text
    if "playlist" in query:
        return await update.message.reply_text("❌ Naeem bhai, playlist link mat bhejien. Analyzing atat jayegi.")
    
    is_url = query.startswith("http")
    status = await update.message.reply_text("🔍 Analyzing request on Cloud...")
    
    try:
        search_query = query if is_url else f"ytsearch1:{query}"
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(search_query, download=False)
            if 'entries' in info: info = info['entries'][0]
        
        video_url = info['webpage_url']
        buttons = [
            [InlineKeyboardButton("🎵 Audio", callback_data=f"mp3|audio|{video_url}")],
            [InlineKeyboardButton("🎥 720p", callback_data=f"mp4|22|{video_url}"),
             InlineKeyboardButton("🎥 1080p", callback_data=f"mp4|137|{video_url}")]
        ]
        await status.edit_text(f"🎬 {info['title'][:40]}...\n\nQuality select karein:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await status.edit_text("❌ Error: Single video link bhejien.")

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    mode, f_id, url = query.data.split("|")
    status_msg = await query.message.reply_text("⏳ F4X Cloud Downloading...")

    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, download_engine, url, mode, f_id if f_id != 'audio' else None)
        
        await status_msg.edit_text("📤 Uploading...")
        with open(file_path, 'rb') as f:
            if mode == 'mp3':
                await query.message.reply_audio(audio=f, caption=OWNER_TAG)
            else:
                await query.message.reply_video(video=f, caption=OWNER_TAG)
        
        if os.path.exists(file_path): os.remove(file_path)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Error: {str(e)[:100]}")

if __name__ == '__main__':
    keep_alive() # Server start
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ Bot is Online for Naeem!")
    app.run_polling()
