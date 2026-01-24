import os, yt_dlp, asyncio, uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# --- CONFIGURATION ---
BOT_TOKEN = "8421035286:AAHAXb-OI-kqiQnM7UL42o1JervTtQFT9fg"
OWNER_TAG = "👑 Owner: Naeem (F4X Empire)"

def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        # Anti-Block: Spoofing as Android & Web
        'extractor_args': {'youtube': {'player_client': ['android', 'web_embedded']}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def download_engine(url, mode, f_id=None):
    uid = str(uuid.uuid4())[:8]
    tmpl = f"f4x_{uid}.%(ext)s"
    opts = {
        'outtmpl': tmpl, 
        'noplaylist': True, 
        'quiet': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Android 14; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0'},
    }
    
    if mode == 'mp3':
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'm4a'}]
    else:
        # High Quality Merging (Render's FFmpeg will handle this)
        opts['format'] = f"{f_id}+bestaudio/best" if f_id else 'bestvideo+bestaudio/best'

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

async def start(update, context):
    await update.message.reply_text(f"🚀 **F4X Ultra Downloader Ready!**\n\nNaeem bhai, link bhejien. 4K tak support hai!\n\n{OWNER_TAG}")

async def handle_msg(update, context):
    query = update.message.text
    if "playlist" in query: return await update.message.reply_text("❌ Playlist not supported.")
    
    st = await update.message.reply_text("🛰️ F4X Engine Analyzing...")
    try:
        info = await asyncio.get_event_loop().run_in_executor(None, get_video_info, query)
        v_url = info['webpage_url']
        formats = info.get('formats', [])
        
        btns = [[InlineKeyboardButton("🎵 Audio (Ultra High)", callback_data=f"mp3|audio|{v_url}")]]
        
        # Quality mapping: 720p, 1080p, 1440p (2K), 2160p (4K)
        res_list = {720: "720p HD", 1080: "1080p Full HD", 1440: "2K Quad HD", 2160: "4K Ultra HD"}
        found_res = []
        
        for res, label in res_list.items():
            for f in formats:
                if f.get('height') == res and res not in found_res:
                    btns.append([InlineKeyboardButton(f"🎥 {label}", callback_data=f"mp4|{f['format_id']}|{v_url}|{res}")])
                    found_res.append(res)
                    break
        
        await st.edit_text(f"🎬 **Title**: {info['title'][:50]}...\n\nSahi quality select karein:", reply_markup=InlineKeyboardMarkup(btns))
    except Exception as e: await st.edit_text(f"❌ Error: Video detail nahi mili.")

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    mode, f_id, url = data[0], data[1], data[2]
    res_val = int(data[3]) if len(data)>3 else 0

    # Device Compatibility Warning for 2K/4K
    if res_val >= 1440:
        await query.message.reply_text(f"⚠️ **Note**: Aapne {res_val}p select kiya hai. Agar aapke phone mein ye video nahi chalti, toh kripya 1080p try karein.")

    st = await query.message.reply_text("⏳ F4X Cloud is Processing (Heavy Task)...")
    try:
        path = await asyncio.get_event_loop().run_in_executor(None, download_engine, url, mode, f_id if f_id != 'audio' else None)
        await st.edit_text("📤 Uploading to Telegram...")
        with open(path, 'rb') as f:
            if mode == 'mp3': await query.message.reply_audio(audio=f, caption=OWNER_TAG)
            else: await query.message.reply_video(video=f, caption=OWNER_TAG, supports_streaming=True)
        if os.path.exists(path): os.remove(path)
        await st.delete()
    except Exception as e: await st.edit_text(f"⚠️ Error: {str(e)[:50]}")

if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()
