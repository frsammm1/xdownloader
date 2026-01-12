import os
import time
import math
import logging
from pyrogram import Client, filters
import yt_dlp

# --- CONFIGURATION (Heroku Env Vars se lega) ---
# Inhe directly code me mat likhna agar repo public ho, 
# lekin private use ke liye yaha string me daal sakte ho ya Heroku Config Vars use karo.
API_ID = int(os.environ.get("API_ID", 123456))  # Apna API ID yahan default me daal sakte ho
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")

# Logging setup (Debugging ke liye)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- PROGRESS BAR FUNCTION ---
async def progress(current, total, message):
    try:
        now = time.time()
        # Update progress every 5 seconds only to avoid floodwait
        if 'last_update_time' not in progress.__dict__:
            progress.last_update_time = 0
        
        if now - progress.last_update_time < 5 and current != total:
            return

        progress.last_update_time = now
        percentage = current * 100 / total
        speed = current / (now - progress.start_time) if now - progress.start_time > 0 else 0
        elapsed_time = int(now - progress.start_time)
        eta = int((total - current) / speed) if speed > 0 else 0
        
        # Human readable file sizes
        def humanbytes(b):
            if not b: return ""
            power = 1024
            n = 0
            dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
            while b > power:
                b /= power
                n += 1
            return str(round(b, 2)) + " " + dic_powerN[n] + 'B'

        text = f"**Uploading...**\n"
        text += f"📊 Progress: {round(percentage, 2)}%\n"
        text += f"📦 Completed: {humanbytes(current)} / {humanbytes(total)}\n"
        text += f"🚀 Speed: {humanbytes(speed)}/s\n"
        text += f"⏳ ETA: {eta} sec"
        
        await message.edit_text(text)
    except Exception as e:
        pass # Ignore minor edit errors

# --- DOWNLOAD LOGIC ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 Hello! Send me any xHamster video link.\nI will download it using your custom cookies.")

@app.on_message(filters.text & ~filters.command("start"))
async def download_video(client, message):
    url = message.text.strip()
    
    # Check if text looks like a URL
    if not url.startswith(("http", "www")):
        await message.reply_text("❌ Please send a valid URL.")
        return

    msg = await message.reply_text("🔎 **Checking URL and extracting metadata...**")
    
    # Temporary directory for downloads
    download_path = "downloads"
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    # Output template (title + extension)
    out_tmpl = f'{download_path}/%(title)s.%(ext)s'

    # yt-dlp Options
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # Try best MP4 first
        'outtmpl': out_tmpl,
        'cookiefile': 'cookies.txt', # Using your provided cookies
        'writethumbnail': True,      # Download thumbnail
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,   # Remove special chars from filename
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', # Fake User Agent
    }

    try:
        # Step 1: Extract Info (JSON) without downloading to check size
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await msg.edit_text("⏳ **Fetching video info...**")
            info_dict = ydl.extract_info(url, download=False)
            
            # Check File Size (Max 2GB for Telegram Bot API limitations usually, but Pyrogram can do 2GB)
            # 2GB = 2 * 1024 * 1024 * 1024 bytes approx 2147483648
            filesize = info_dict.get('filesize') or info_dict.get('filesize_approx')
            
            if filesize and filesize > 2100000000: # ~1.95 GB limit margin
                await msg.edit_text(f"❌ **File too large!**\nSize: {filesize / (1024*1024)} MB.\nTelegram limit is 2GB.")
                return
            
            title = info_dict.get('title', 'Video')
            duration = info_dict.get('duration', 0)
            
            await msg.edit_text(f"📥 **Downloading:** `{title}`\n\nPlease wait, this depends on server speed...")
            
            # Step 2: Real Download
            error_code = ydl.download([url])
            
            if error_code != 0:
                raise Exception("Download failed with error code.")

            # Find the downloaded file
            info_dict = ydl.extract_info(url, download=False) # Re-extract to get final filename
            filename = ydl.prepare_filename(info_dict)
            
            # Thumbnails handling
            thumb_path = filename.rsplit(".", 1)[0] + ".webp"
            if not os.path.exists(thumb_path):
                 thumb_path = filename.rsplit(".", 1)[0] + ".jpg"
            if not os.path.exists(thumb_path):
                thumb_path = None

    except Exception as e:
        await msg.edit_text(f"❌ **Error:** {str(e)}")
        return

    # --- UPLOAD LOGIC ---
    try:
        progress.start_time = time.time()
        await msg.edit_text("📤 **Uploading to Telegram...**")
        
        # Send Video
        await client.send_video(
            chat_id=message.chat.id,
            video=filename,
            caption=f"🎥 **{title}**\n\n✅ Downloaded via Bot",
            duration=duration,
            thumb=thumb_path,
            supports_streaming=True,
            progress=progress,
            progress_args=(msg,)
        )
        
        await msg.delete() # Delete "Uploading" message after success
        
    except Exception as e:
        await msg.edit_text(f"❌ **Upload Failed:** {str(e)}")
    
    finally:
        # --- CLEANUP (Space free karna bahut zaruri hai Heroku pe) ---
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)
        if 'thumb_path' in locals() and thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
  
