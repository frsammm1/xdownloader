import os
import time
import logging
import asyncio
import shutil

# --- FIX FOR PYTHON 3.10+ CRASH (VERY IMPORTANT) ---
# Ye code start hone se pehle Event Loop create karega
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# ---------------------------------------------------

from pyrogram import Client, filters
import yt_dlp

# --- CONFIGURATION (Heroku Config Vars) ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "YOUR_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- PROGRESS BAR FUNCTION ---
async def progress(current, total, message):
    try:
        now = time.time()
        # Progress bar state maintain karne ke liye
        if 'last_update_time' not in progress.__dict__:
            progress.last_update_time = 0
        
        # 5 second ka gap taaki FloodWait na aaye
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

# --- START COMMAND ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 **Bot Online!**\nSend me any xHamster link to download.")

# --- DOWNLOAD LOGIC ---
@app.on_message(filters.text & ~filters.command("start"))
async def download_handler(client, message):
    url = message.text.strip()
    
    # Check if text is a link
    if not url.startswith(("http", "www")):
        return 

    status_msg = await message.reply_text("🔎 **Analyzing Link...**")
    
    # Create unique folder for each task
    timestamp = int(time.time())
    download_path = f"downloads/{timestamp}"
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    out_tmpl = f'{download_path}/%(title)s.%(ext)s'

    # yt-dlp Configuration
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_tmpl,
        'cookiefile': 'cookies.txt', # Cookies ka use karega
        'writethumbnail': True,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36',
    }

    filename = None
    thumb_path = None

    try:
        # Step 1: Check Metadata & Size
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await status_msg.edit_text("⏳ **Fetching Info...**")
            info = ydl.extract_info(url, download=False)
            
            # 2GB Limit Check (Telegram Limit)
            filesize = info.get('filesize') or info.get('filesize_approx')
            if filesize and filesize > 2000000000:
                await status_msg.edit_text(f"❌ **File too big!**\nSize > 2GB. Cannot upload.")
                # Cleanup folder
                shutil.rmtree(download_path, ignore_errors=True)
                return

            title = info.get('title', 'Video')
            duration = info.get('duration', 0)
            
            # Step 2: Download
            await status_msg.edit_text(f"⬇️ **Downloading:** `{title}`\nPlease wait...")
            error_code = ydl.download([url])
            
            if error_code != 0:
                raise Exception("Download failed.")

            # Get actual filename
            info = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info)
            
            # Find Thumbnail
            base_name = filename.rsplit(".", 1)[0]
            if os.path.exists(base_name + ".webp"):
                thumb_path = base_name + ".webp"
            elif os.path.exists(base_name + ".jpg"):
                thumb_path = base_name + ".jpg"

    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** {str(e)}")
        shutil.rmtree(download_path, ignore_errors=True)
        return

    # Step 3: Upload
    try:
        await status_msg.edit_text("📤 **Uploading to Telegram...**")
        progress.start_time = time.time()
        
        await client.send_video(
            chat_id=message.chat.id,
            video=filename,
            caption=f"🎥 **{title}**\n✅ Downloaded via Bot",
            duration=duration,
            thumb=thumb_path,
            supports_streaming=True,
            progress=progress,
            progress_args=(status_msg,)
        )
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ **Upload Failed:** {str(e)}")

    finally:
        # Step 4: Cleanup (Delete folder)
        if os.path.exists(download_path):
            shutil.rmtree(download_path, ignore_errors=True)

# --- ENTRY POINT (Ye bot ko start rakhega) ---
if __name__ == "__main__":
    print("Bot Started Successfully!")
    app.run()
        
