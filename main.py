import os
import time
import logging
import asyncio
import shutil

# --- FIX FOR PYTHON 3.10+ CRASH (MANDATORY) ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# ----------------------------------------------

from pyrogram import Client, filters
import yt_dlp

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "YOUR_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- PROGRESS BAR ---
async def progress(current, total, message):
    try:
        now = time.time()
        if 'last_update_time' not in progress.__dict__:
            progress.last_update_time = 0
        
        # 5 sec delay to avoid floodwait
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
    await message.reply_text("👋 **Bot Online!**\nSend me the xHamster link.")

@app.on_message(filters.text & ~filters.command("start"))
async def download_handler(client, message):
    url = message.text.strip()
    
    if not url.startswith(("http", "www")):
        return 

    status_msg = await message.reply_text("🔎 **Analyzing Link...**\n(Updating extractors if needed...)")
    
    # Unique Folder
    timestamp = int(time.time())
    download_path = f"downloads/{timestamp}"
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    out_tmpl = f'{download_path}/%(title)s.%(ext)s'

    # UPDATED User-Agent and Options
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_tmpl,
        'cookiefile': 'cookies.txt', 
        'writethumbnail': True,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        # Updated User Agent (Chrome 120) to look like a real PC
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        # Agar specific extractor fail ho, to generic try kare
        'ignoreerrors': True, 
    }

    filename = None
    thumb_path = None

    try:
        # Step 1: Info & Size Check
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await status_msg.edit_text("⏳ **Fetching Info...**")
            
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                # Agar extraction fail ho, to error print kare
                await status_msg.edit_text(f"❌ **Extraction Failed:**\n`{str(e)}`\n\nTry checking the link.")
                shutil.rmtree(download_path, ignore_errors=True)
                return

            # Check if info is None
            if not info:
                await status_msg.edit_text("❌ **Error:** Video not found or link invalid.")
                shutil.rmtree(download_path, ignore_errors=True)
                return

            # 2GB Limit Check
            filesize = info.get('filesize') or info.get('filesize_approx')
            if filesize and filesize > 2000000000:
                await status_msg.edit_text(f"❌ **File > 2GB.** Cannot upload on Telegram.")
                shutil.rmtree(download_path, ignore_errors=True)
                return

            title = info.get('title', 'Video')
            duration = info.get('duration', 0)
            
            # Step 2: Download
            await status_msg.edit_text(f"⬇️ **Downloading:** `{title}`")
            error_code = ydl.download([url])
            
            # Re-verify file existence
            info = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info)
            
            if not os.path.exists(filename):
                # Kabhi kabhi format change hone par extension badal jati hai
                # Check for any file in folder
                files = os.listdir(download_path)
                if files:
                    for f in files:
                        if f.endswith(('.mp4', '.mkv', '.webm')):
                            filename = os.path.join(download_path, f)
                            break
            
            if not filename or not os.path.exists(filename):
                 raise Exception("File not downloaded.")

            # Thumbnail
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
