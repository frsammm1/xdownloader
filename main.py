import os
import time
import logging
import asyncio
import shutil

# --- FIX FOR PYTHON 3.10+ CRASH ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# ----------------------------------

from pyrogram import Client, filters
import yt_dlp

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "YOUR_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN")

logging.basicConfig(level=logging.INFO)

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- PROGRESS BAR ---
async def progress(current, total, message):
    try:
        now = time.time()
        if 'last_update_time' not in progress.__dict__:
            progress.last_update_time = 0
        
        if now - progress.last_update_time < 5 and current != total:
            return

        progress.last_update_time = now
        percentage = current * 100 / total
        
        def humanbytes(b):
            if not b: return ""
            power = 1024
            n = 0
            dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
            while b > power:
                b /= power
                n += 1
            return str(round(b, 2)) + " " + dic_powerN[n] + 'B'

        text = f"**🚀 Uploading...**\n"
        text += f"📊 Progress: {round(percentage, 2)}%\n"
        text += f"📦 Size: {humanbytes(current)} / {humanbytes(total)}"
        
        await message.edit_text(text)
    except Exception:
        pass

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 **Bot Online!**\nSend xHamster link.")

# --- HELPER FUNCTION TO DOWNLOAD ---
def run_download(url, path, generic_mode=False):
    out_tmpl = f'{path}/%(title)s.%(ext)s'
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_tmpl,
        'cookiefile': 'cookies.txt', 
        'writethumbnail': True,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    # IMPORTANT: Agar Normal fail hua to Generic Mode ON karenge
    if generic_mode:
        ydl_opts['force_generic_extractor'] = True
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return info, filename

@app.on_message(filters.text & ~filters.command("start"))
async def download_handler(client, message):
    url = message.text.strip()
    
    if not url.startswith(("http", "www")):
        return 

    status_msg = await message.reply_text("🔎 **Checking Link...**")
    
    timestamp = int(time.time())
    download_path = f"downloads/{timestamp}"
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    filename = None
    thumb_path = None
    title = "Video"
    duration = 0

    try:
        # ATTEMPT 1: Normal Download
        await status_msg.edit_text("⏳ **Trying Method 1 (Standard)...**")
        info, filename = await asyncio.to_thread(run_download, url, download_path, False)
        
        title = info.get('title', 'Video')
        duration = info.get('duration', 0)

    except Exception as e:
        error_text = str(e)
        # Agar 'videoModel' ya koi bhi extractor error aaye, to Plan B use karega
        print(f"Method 1 Failed: {error_text}")
        
        try:
            # ATTEMPT 2: Generic Mode (Force Backup)
            await status_msg.edit_text("⚠️ **Method 1 Failed.**\n🔄 Trying Method 2 (Generic Mode)...")
            info, filename = await asyncio.to_thread(run_download, url, download_path, True)
            
            title = info.get('title', 'Video')
            duration = info.get('duration', 0)
            
        except Exception as e2:
            # Agar dono fail ho gaye
            await status_msg.edit_text(f"❌ **Failed:** {str(e2)}")
            shutil.rmtree(download_path, ignore_errors=True)
            return

    # --- FILE CHECK & THUMBNAIL ---
    if not filename or not os.path.exists(filename):
         # Kabhi kabhi generic extractor filename alag deta hai
         files = os.listdir(download_path)
         if files:
            for f in files:
                if f.endswith(('.mp4', '.mkv', '.webm')):
                    filename = os.path.join(download_path, f)
                    break

    if not filename or not os.path.exists(filename):
        await status_msg.edit_text("❌ Error: File downloaded but not found.")
        shutil.rmtree(download_path, ignore_errors=True)
        return
        
    # Check Size (2GB Limit)
    if os.path.getsize(filename) > 2000000000:
        await status_msg.edit_text("❌ File > 2GB. Cannot upload.")
        shutil.rmtree(download_path, ignore_errors=True)
        return

    # Thumbnail Finding
    base_name = filename.rsplit(".", 1)[0]
    if os.path.exists(base_name + ".webp"):
        thumb_path = base_name + ".webp"
    elif os.path.exists(base_name + ".jpg"):
        thumb_path = base_name + ".jpg"

    # --- UPLOAD ---
    try:
        await status_msg.edit_text("📤 **Uploading...**")
        progress.start_time = time.time()
        
        await client.send_video(
            chat_id=message.chat.id,
            video=filename,
            caption=f"🎥 **{title}**",
            duration=duration,
            thumb=thumb_path,
            supports_streaming=True,
            progress=progress,
            progress_args=(status_msg,)
        )
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ **Upload Error:** {str(e)}")

    finally:
        if os.path.exists(download_path):
            shutil.rmtree(download_path, ignore_errors=True)

if __name__ == "__main__":
    app.run()
