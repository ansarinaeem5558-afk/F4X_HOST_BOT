import os, yt_dlp, asyncio, uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# --- CONFIGURATION ---
BOT_TOKEN = "8421035286:AAHAXb-OI-kqiQnM7UL42o1JervTtQFT9fg"
OWNER_TAG = "👑 Owner: Naeem (F4X Empire)"

def download_engine(url, mode, f_id=None):
    uid = str(uuid.uuid4())[:8]
    tmpl = f"f4x_{uid}.%(ext)s"
    opts = {
        'outtmpl': tmpl, 'noplaylist': True, 'quiet': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    if mode == 'mp3':
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'm4a'}]
    else:
        # High quality merging ke liye FFmpeg zaroori hai
        opts['format'] = f"{f_id}+bestaudio/best" if f_id else 'bestvideo+bestaudio/best'

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

async def start(update, context):
    await update.message.reply_text(f"🔥 **F4X Cloud Bot Ready!**\nNaeem bhai, link bhejien ya gane ka naam likhein.\n\n{OWNER_TAG}")

async def handle_msg(update, context):
    query = update.message.text
    if "playlist" in query: return await update.message.reply_text("❌ Playlist allowed nahi hai.")
    status = await update.message.reply_text("🔍 Analyzing request...")
    try:
        is_url = query.startswith("http")
        s_query = query if is_url else f"ytsearch1:{query}"
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(s_query, download=False)
            if 'entries' in info: info = info['entries'][0]
        v_url = info['webpage_url']
        btns = [[InlineKeyboardButton("🎵 Audio", callback_data=f"mp3|audio|{v_url}")],
                [InlineKeyboardButton("🎥 720p", callback_data=f"mp4|22|{v_url}"),
                 InlineKeyboardButton("🎥 1080p", callback_data=f"mp4|137|{v_url}")]]
        await status.edit_text(f"🎬 {info['title'][:40]}...\n\nSelect Quality:", reply_markup=InlineKeyboardMarkup(btns))
    except: await status.edit_text("❌ Nahi mila bhai.")

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    mode, f_id, url = query.data.split("|")
    st = await query.message.reply_text("⏳ F4X Cloud Downloading...")
    try:
        path = await asyncio.get_event_loop().run_in_executor(None, download_engine, url, mode, f_id if f_id != 'audio' else None)
        await st.edit_text("📤 Uploading...")
        with open(path, 'rb') as f:
            if mode == 'mp3': await query.message.reply_audio(audio=f, caption=OWNER_TAG)
            else: await query.message.reply_video(video=f, caption=OWNER_TAG)
        if os.path.exists(path): os.remove(path)
        await st.delete()
    except Exception as e: await st.edit_text(f"⚠️ Error: {str(e)[:50]}")

if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(CallbackQueryHandler(button_handler)); app.run_polling()
